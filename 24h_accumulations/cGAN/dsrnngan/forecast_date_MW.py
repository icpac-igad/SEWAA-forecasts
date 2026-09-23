#!/usr/bin/env python
# coding: utf-8


# Same as forecast.py, but the date to process is given as a command line argument

# Big warning:
# This is not a general-purpose forecast script.
# This is for forecasting on the pre-defined 'ICPAC region' (e.g., the latitudes
# and longitudes are hard-coded), and assumes the input forecast data starts at
# time 0, with time steps of data.HOURS.
# A more robust version of this script would parse the latitudes, longitudes, and
# forecast time info from the input file.
# The forecast data fields must match those defined in data.all_fcst_fields

import os
import argparse
import pathlib
import yaml
from datetime import datetime, date, timedelta
import properscoring as ps

import netCDF4 as nc
import numpy as np
from tensorflow.keras.utils import Progbar

from data import HOURS, all_fcst_fields, fcst_norm, denormalise, load_hires_constants, load_fcst, load_fcst_operational, load_truth_and_mask, load_fcst_norm, climatology_channel, sanitise_fcst_input
import read_config
import models
from noise import NoiseGenerator
from setupmodel import setup_model


#Change these forecast dates (defaults; a PERIOD block in the yaml overrides them)
start_date = date(2020, 6, 1)
end_date   = date(2020, 12, 31)
log_precip = True

# Some setup
read_config.set_gpu_mode()  # set up whether to use GPU, and mem alloc mode
data_paths = read_config.get_data_paths()  # need the constants directory
downscaling_steps = read_config.read_downscaling_factor()["steps"]

# Open and parse forecast.yaml
parser = argparse.ArgumentParser()
parser.add_argument(
    "yaml_file",
    nargs="?",
    default="forecast.yaml",
    help="Path to forecast configuration YAML file."
)
parser.add_argument(
    "date",
    nargs="?",
    default=None,
    help="Optional YYYYMMDD; overrides the config PERIOD to this single date "
         "(for the operational per-date daily runner)."
)
args = parser.parse_args()

with open(args.yaml_file, "r") as f:
    try:
        fcst_params = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        print(exc)
        raise

model_folder = fcst_params["MODEL"]["folder"]
checkpoint = fcst_params["MODEL"]["checkpoint"]
include_cape = fcst_params["MODEL"]["include_cape"]
fcst_input_folder = fcst_params["INPUT"]["fcst_folder"]
truth_input_folder = fcst_params["INPUT"]["truth_folder"]
constants_folder = fcst_params["INPUT"]["constants_folder"]
normalisation_folder = fcst_params["INPUT"]["normalisation_folder"]
output_folder = fcst_params["OUTPUT"]["folder"]
ensemble_members = fcst_params["OUTPUT"]["ensemble_members"]
save_crps_only = fcst_params["OUTPUT"]["save_crps_only"]

# INPUT.format: "training" (per-field yearly files; the held-out/eval path, default) or
# "operational" (one IFS_<date>_00Z.nc per day; the live gbmc->Oxford feed). Operational
# reads via data.load_fcst_operational, which mirrors load_fcst's window/units/normalisation
# exactly, so the model sees identically-scaled inputs either way. For operational,
# INPUT.fcst_folder is the folder holding the IFS_<date>_00Z.nc files.
input_format = fcst_params["INPUT"].get("format", "training")
assert input_format in ("training", "operational"), f"INPUT.format={input_format!r}"

# OUTPUT.histogram_folder: if set, also write the per-pixel ensemble histogram counts the
# web interface consumes (counts_<date>_00_<lead>h.nc), computed in-memory from the same
# 50-member ensemble -- so one run produces both the forecast and the interface data.
# Absent -> no histogram (default), keeping the eval/held-out behaviour unchanged.
histogram_folder = fcst_params["OUTPUT"].get("histogram_folder", None)
# Log-scale rainfall bins (mm/h), identical to forecast2histogram_7d_lowRAM.py so the
# interface reads these counts the same way as the operational IMERG ones.
BIN_SPEC = np.array([0., 0.04166667, 0.08333333, 0.20833333, 0.41666667, 0.625, 0.83333333,
                     1., 1.25, 1.5, 1.8, 2.2, 2.6, 3., 3.5, 4., 4.7, 5.4, 6.1, 7., 8., 9.,
                     10., 11.5, 13.25, 15., 1000.])

# Date resolution order: command-line date (single day, for the daily runner) wins;
# else the config PERIOD block; else the start_date/end_date defaults above.
if args.date:
    start_date = end_date = datetime.strptime(args.date, "%Y%m%d").date()
elif "PERIOD" in fcst_params:
    start_date = datetime.strptime(str(fcst_params["PERIOD"]["start"]), "%Y%m%d").date()
    end_date   = datetime.strptime(str(fcst_params["PERIOD"]["end"]),   "%Y%m%d").date()
print(f"forecast period: {start_date} to {end_date}")

local_fcst_norm = load_fcst_norm(year=2018, normalisation_path=normalisation_folder)
assert local_fcst_norm is not None

#Set up fcst_fields --     # needed for now as Oxford's ARC only has 13 variables
# MODEL.field_set picks the input set explicitly; without it the old include_cape
# boolean still decides, so existing yamls behave exactly as before.
#   14field  run06     (13 IFS + cape = 28 ch)
#   run07    run07     (13 IFS + climatology as 1st field = 28 ch; climatology loaded
#                       from IFS file in operational mode, from training files otherwise)
#   13field  run08/run09/run10  (cape dropped 2026-07-16, data.py:33)
#   run11    run11/run13  (13 IFS + RFE climatology appended = 28 ch)
#   4field   run05
field_set = fcst_params["MODEL"].get("field_set",
                                     "14field" if include_cape else "4field")

# clim_channels: extra climatology input channels appended AFTER the IFS fields.
#   0 = none;  2 = run11's climatological mean+sd (from data.climatology_channel).
# run11 is 13 IFS fields (26 ch) + 2 climatology = 28 channels.
clim_channels = 0
if field_set == "14field":
    all_fcst_fields = ['cape', 'cp', 'mcc', 'sp', 'ssr', 't2m', 'tciw', 'tclw', 'tcrw', 'tcw', 'tcwv', 'tp', 'u700', 'v700']
    accumulated_fields = ['cp', 'ssr', 'tp']
    nonnegative_fields = ['cape', 'cp', 'mcc', 'sp', 'ssr', 't2m', 'tciw', 'tclw', 'tcrw', 'tcw', 'tcwv', 'tp'] #MW: things that can't be below 0
elif field_set == "run07":
    # CHIRPS run07: 14 fields with climatology as the 1st field (not cape). 28 channels.
    # In operational mode, climatology_ensemble_mean/sd are read from the IFS file
    # (Oxford publishes them alongside the standard IFS fields for this model).
    all_fcst_fields = ['climatology', 'cp', 'mcc', 'sp', 'ssr', 't2m', 'tciw', 'tclw', 'tcrw', 'tcw', 'tcwv', 'tp', 'u700', 'v700']
    accumulated_fields = ['cp', 'ssr', 'tp']
    nonnegative_fields = ['climatology', 'cp', 'mcc', 'sp', 'ssr', 't2m', 'tciw', 'tclw', 'tcrw', 'tcw', 'tcwv', 'tp']
elif field_set in ("13field", "run11"):
    all_fcst_fields = ['cp', 'mcc', 'sp', 'ssr', 't2m', 'tciw', 'tclw', 'tcrw', 'tcw', 'tcwv', 'tp', 'u700', 'v700']
    accumulated_fields = ['cp', 'ssr', 'tp']
    nonnegative_fields = ['cp', 'mcc', 'sp', 'ssr', 't2m', 'tciw', 'tclw', 'tcrw', 'tcw', 'tcwv', 'tp']
    if field_set == "run11":
        clim_channels = 2   # + RFE climatology mean & sd, appended in the build loop below
elif field_set == "4field":
    # run05: model trained on ONLY these 4 IFS fields
    all_fcst_fields = ['tp', 't2m', 'tcwv', 'sp']
    accumulated_fields = ['tp']
    nonnegative_fields = ['tp', 'tcwv'] #MW: things that can't be below 0
else:
    raise ValueError(f"MODEL.field_set must be 14field/run07/13field/4field/run11, got {field_set!r}")
print(f"field set: {field_set} ({len(all_fcst_fields)} fields + {clim_channels} clim = {2*len(all_fcst_fields)+clim_channels} channels)")

# Open and parse GAN config file
config_path = os.path.join(model_folder, "setup_params.yaml")
with open(config_path, "r") as f:
    try:
        setup_params = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        print(exc)

mode = setup_params["GENERAL"]["mode"]
arch = setup_params["MODEL"]["architecture"]
padding = setup_params["MODEL"]["padding"]
filters_gen = setup_params["GENERATOR"]["filters_gen"]
noise_channels = setup_params["GENERATOR"]["noise_channels"]
latent_variables = setup_params["GENERATOR"]["latent_variables"]
filters_disc = setup_params["DISCRIMINATOR"]["filters_disc"]
# TODO: avoid setting up discriminator in forecast mode?
constant_fields = 2

assert mode == "GAN", "standalone forecast script only for GAN, not VAE-GAN or deterministic model"

# Set up pre-trained GAN
weights_fn = os.path.join(model_folder, "models", f"gen_weights-{checkpoint:07}.h5")
input_channels = 2*len(all_fcst_fields) + clim_channels

# Inference only: build the generator directly. Using setup_model() would also
# build the discriminator + WGAN-GP training graph, which is not needed here and
# fails to construct under this TF/Keras version (RandomWeightedAverage).
gen = models.generator(mode=mode,
                       arch=arch,
                       downscaling_steps=downscaling_steps,
                       input_channels=input_channels,
                       constant_fields=constant_fields,
                       filters_gen=filters_gen,
                       noise_channels=noise_channels,
                       latent_variables=latent_variables,
                       padding=padding)
print(weights_fn)
gen.load_weights(weights_fn)

network_const_input = load_hires_constants(batch_size=1, constants_path=constants_folder)  # 1 x lats x lons x 2


def create_output_file(nc_out_path):
    netcdf_dict = {}
    rootgrp = nc.Dataset(nc_out_path, "w", format="NETCDF4")
    netcdf_dict["rootgrp"] = rootgrp
    rootgrp.description = "GAN 24-hour rainfall ensemble members in the ICPAC region."

    # Create output file dimensions
    rootgrp.createDimension("latitude", len(latitude))
    rootgrp.createDimension("longitude", len(longitude))
    rootgrp.createDimension("time", None)
    rootgrp.createDimension("valid_time", None)

    if not save_crps_only:
        rootgrp.createDimension("member", ensemble_members)

    # Create coordinate variables
    latitude_data = rootgrp.createVariable("latitude", "f4", ("latitude",))
    latitude_data.units = "degrees_north"
    latitude_data[:] = latitude

    longitude_data = rootgrp.createVariable("longitude", "f4", ("longitude",))
    longitude_data.units = "degrees_east"
    longitude_data[:] = longitude

    if not save_crps_only:
        ensemble_data = rootgrp.createVariable("member", "i4", ("member",))
        ensemble_data.units = "ensemble member"
        ensemble_data[:] = range(1, ensemble_members + 1)

    netcdf_dict["time_data"] = rootgrp.createVariable("time", "f4", ("time",))
    netcdf_dict["time_data"].units = "hours since 1900-01-01 00:00:00.0"

    netcdf_dict["valid_time_data"] = rootgrp.createVariable(
        "fcst_valid_time", "f4", ("time", "valid_time")
    )
    netcdf_dict["valid_time_data"].units = "hours since 1900-01-01 00:00:00.0"

    # Ensemble precipitation output
    if not save_crps_only:
        netcdf_dict["precipitation"] = rootgrp.createVariable(
            "precipitation",
            "f4",
            ("time", "member", "valid_time", "latitude", "longitude"),
            compression="zlib",
            chunksizes=(1, 1, 1, len(latitude), len(longitude)),
        )
        netcdf_dict["precipitation"].units = "mm/h"
        netcdf_dict["precipitation"].long_name = "Precipitation"

    # CRPS output
    netcdf_dict["crps"] = rootgrp.createVariable(
        "crps",
        "f4",
        ("time", "valid_time", "latitude", "longitude"),
        compression="zlib",
        chunksizes=(1, 1, len(latitude), len(longitude)),
    )
    netcdf_dict["crps"].units = "mm/h"
    netcdf_dict["crps"].long_name = "Spatial mean CRPS for precipitation"

    return netcdf_dict

def iter_dates(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)

#Iterate through all dates that we want to forecast/CRPS
for d in iter_dates(start_date, end_date):

    # Truth (RFE2 at D+1) is needed only to SCORE. In eval/held-out mode a missing truth
    # means we can't score, so skip the date. In OPERATIONAL mode we still produce the
    # forecast + histogram (a live forecast has no truth yet); CRPS is just skipped.
    _truth_dt = d + timedelta(days=int(HOURS) // 24)   # LEAD_IDX=1 day
    _truth_p = os.path.join(truth_input_folder, str(_truth_dt.year), f"{_truth_dt:%Y%m%d}.nc")
    _have_truth = os.path.exists(_truth_p)
    if not _have_truth and input_format != "operational":
        print(f"skip {d:%Y%m%d}: truth {_truth_dt:%Y%m%d}.nc missing")
        continue

    # Open input netCDF file to get the times
    if input_format == "operational":
        file_name = os.path.join(fcst_input_folder, f"IFS_{d.strftime('%Y%m%d')}_00Z.nc")
    else:
        file_name = os.path.join(fcst_input_folder, str(d.year), "tp.nc")
    with nc.Dataset(file_name, mode="r") as nc_in:
        start_times = nc_in["time"][:]
        valid_times = nc_in["valid_time"][:] if input_format == "operational" else nc_in["fcst_valid_time"][:]
        latitude = nc_in["latitude"][:]
        longitude = nc_in["longitude"][:]
    # nc_in.close()

    # The datetime corresponding to this start time
    # d = datetime(1900,1,1) + timedelta(hours=int(start_times[0]))

    # Create output netCDF file
    pathlib.Path(output_folder).mkdir(parents=True, exist_ok=True)
    if not save_crps_only:
        nc_out_path = os.path.join(output_folder, f"GAN_fcst_crps_{d.year}{d.month:02d}{d.day:02d}_00Z.nc")
    elif save_crps_only:
        nc_out_path = os.path.join(output_folder, f"GAN_crps_{d.year}{d.month:02d}{d.day:02d}_00Z.nc")
    netcdf_dict = create_output_file(nc_out_path)

    # copy across valid_time from input file
    # For 7x 24h forecasts with lead times of 6, 30, 54, 78, 102, 126, 150 hours
    # in_time_idx = ([1,5,9,13,17,21,25],)
    # Locate the date on the file's own time axis (partial-year files like 2023/2024
    # start on Jun 1, so day-of-year would pick the wrong step). See data.load_fcst.
    if input_format == "operational":
        # single-day operational file: one start time, 1D valid_time axis of 30 steps
        fcst_idx = 0
        netcdf_dict["time_data"][0] = start_times[0]
        # 7 lead days like the operational product (in_time_idx = [1,5,9,13,17,21,25]).
        # valid_time_num=0 is the validated D+1; leads 1-6 (D+2..D+7) are out-of-distribution.
        _in_time_idx = [1, 5, 9, 13, 17, 21, 25]
        valid_times_forecast = valid_times[_in_time_idx]
    else:
        _ftimes = nc.num2date(start_times, nc.Dataset(file_name)["time"].units)
        _want = d.strftime("%Y%m%d")
        _matches = [i for i, x in enumerate(_ftimes) if x.strftime("%Y%m%d") == _want]
        if not _matches:
            print(f"  {_want} not in {file_name}, skipping")
            netcdf_dict["rootgrp"].close(); os.remove(nc_out_path); continue
        fcst_idx = _matches[0]
        netcdf_dict["time_data"][0] = start_times[fcst_idx]
        valid_time_idx = ([5],) #for 1x24h forecast with lead time 30h
        valid_times_forecast = valid_times[fcst_idx, valid_time_idx]
    print(np.shape(valid_times_forecast))
    netcdf_dict["valid_time_data"][0,:] = valid_times_forecast

    # For each valid time
    skip_this_date = False   # set if a corrupt input makes this date unusable
    for valid_time_num in range(len(valid_times_forecast)):

        # the contents of the next loop are v. similar to load_fcst from data.py,
        # but not quite the same, since that has different assumptions on how the
        # forecast data is stored.  TODO: unify the data normalisation between these?
        field_arrays = []
        if input_format == "operational":
            # live feed: one IFS_<date>_00Z.nc holding all fields as {field}_ensemble_mean
            ifs_path = os.path.join(fcst_input_folder, f"IFS_{d.strftime('%Y%m%d')}_00Z.nc")
            _ifs = nc.Dataset(ifs_path, mode="r")
            _ifs_vars = set(_ifs.variables.keys())
            for field in all_fcst_fields:
                if f"{field}_ensemble_mean" not in _ifs_vars:
                    # Field not in operational IFS file (e.g. 'climatology' for run07).
                    # Fill with zeros (normalised-space mean) so the model runs on the
                    # remaining real IFS fields. A proper climatology file should be
                    # deployed for production quality.
                    _sample = list(_ifs_vars)[0]
                    _shape = _ifs[_sample].shape[1:]  # (lat, lon)
                    _zeros = np.zeros((*_shape, 2), dtype=np.float32)
                    field_arrays.append(_zeros)
                    print(f"WARNING: {field} not in IFS file, using zero-fill placeholder")
                else:
                    field_arrays.append(load_fcst_operational(
                        field, _ifs, valid_time_num=valid_time_num, log_precip=log_precip, norm=True,
                        fcst_norm_dict=local_fcst_norm))
            _ifs.close()
        else:
            for field in all_fcst_fields:
                field_arrays.append(load_fcst(
                    field, d.strftime('%Y%m%d'), 0, log_precip=log_precip, norm=True,
                    fcst_path=fcst_input_folder, fcst_norm_dict=local_fcst_norm))

        # for j, field in enumerate(all_fcst_fields):
        #     arr = field_arrays[j]
        #     print(field, arr.min(), arr.max(), arr.mean())

        # print("const input:", network_const_input.min(), network_const_input.max(), network_const_input.mean())
        
        network_fcst_input = np.concatenate(field_arrays, axis=-1)  # lat x lon x 2*len(all_fcst_fields)
        if clim_channels:
            # run11: append RFE climatology mean+sd for this date, matching how
            # data.load_fcst_stack builds the training input (same log10(1+x) norm,
            # indexed by the day being predicted). Gives 2*13 + 2 = 28 channels.
            # climatology_channel() raises if RFE_climatology_meansd_doy.nc hasn't been
            # deployed into the constants dir yet; fall back to zero-fill (same treatment
            # as a field missing from the operational IFS file, above) so the pipeline still
            # produces a forecast + histogram rather than hard-failing on every RFE run.
            try:
                clim = climatology_channel(d.strftime('%Y%m%d'), lead_days=valid_time_num)
            except (FileNotFoundError, OSError) as e:
                print(f"WARNING: RFE climatology unavailable ({e}); using zero-fill "
                      f"placeholder for the {clim_channels} climatology channel(s).")
                clim = np.zeros(network_fcst_input.shape[:-1] + (clim_channels,), dtype=np.float32)
            network_fcst_input = np.concatenate([network_fcst_input, clim], axis=-1)

        # Guard against corrupt IFS fields (e.g. all-NaN u700/v700 on 2024-01-28). Without
        # this a NaN channel poisons the day's GAN CRPS and the running mean. sanitise fills
        # isolated NaNs with the normalised field mean (0); if a critical field is dead we
        # skip scoring this date entirely -- the correct, automatic form of what used to be
        # a manual "drop that day" after the fact.
        network_fcst_input, _usable, _rep = sanitise_fcst_input(
            network_fcst_input, all_fcst_fields, d.strftime('%Y%m%d'), clim_channels=clim_channels)
        if _rep["dead_fields"]:
            print(f"WARNING: corrupt IFS input on {d.strftime('%Y%m%d')}: {_rep['dead_fields']}", flush=True)
        if not _usable:
            print(f"SKIPPING CRPS for {d.strftime('%Y%m%d')}: critical field(s) NaN "
                  f"({_rep['dead_fields']}). Day excluded from scoring.", flush=True)
            skip_this_date = True
            break   # file is closed and removed once, after the loop (below)

        network_fcst_input = np.expand_dims(network_fcst_input, axis=0)  # 1 x lat x lon x C
        
        noise_shape = network_fcst_input.shape[1:-1] + (noise_channels,)
        noise_gen = NoiseGenerator(noise_shape, batch_size=1)
        z = noise_gen()
        # print("noise:", z.min(), z.max(), z.mean())
        progbar = Progbar(ensemble_members)

        ens_cgan_preds = []
        for ii in range(ensemble_members):
            gan_inputs = [network_fcst_input, network_const_input, noise_gen()]
            gan_prediction = gen.predict(gan_inputs, verbose=False)  # 1 x lat x lon x 1
            pred = denormalise(gan_prediction[0, :, :, 0])
            if not save_crps_only:
                netcdf_dict["precipitation"][0, ii, valid_time_num, :, :] = pred
            
            ens_cgan_preds.append(pred)
            progbar.add(1)
            

        ens_cgan_preds_stacked = np.stack(ens_cgan_preds, axis=0)

        # ---- optional: per-pixel ensemble histogram counts for the web interface ----
        # Computed here from the in-memory ensemble (members, lat, lon), so one run yields
        # both the forecast and the interface data. Format matches forecast2histogram, so
        # the interface reads it identically to the operational IMERG counts.
        if histogram_folder:
            _ens = ens_cgan_preds_stacked                    # (members, lat, lon), mm/hr
            _idx = np.digitize(_ens, BIN_SPEC) - 1           # bin index per member per pixel
            _counts = np.zeros((len(BIN_SPEC) - 1, _ens.shape[1], _ens.shape[2]), dtype=np.int16)
            for _b in range(len(BIN_SPEC) - 1):
                _counts[_b] = (_idx == _b).sum(axis=0)
            _lead_h = valid_time_num * 24 + 6                # 6h label for the D+1 lead
            _yr = d.strftime('%Y')
            pathlib.Path(os.path.join(histogram_folder, _yr)).mkdir(parents=True, exist_ok=True)
            _cpath = os.path.join(histogram_folder, _yr,
                                  f"counts_{d.strftime('%Y%m%d')}_00_{_lead_h}h.nc")
            _cg = nc.Dataset(_cpath, "w", format="NETCDF4")
            _cg.description = "cGAN-RFE (run11) forecast histogram counts"
            _cg.createDimension("longitude", len(longitude))
            _cg.createDimension("latitude", len(latitude))
            _cg.createDimension("time", 1)
            _cg.createDimension("valid_time", 1)
            _cg.createDimension("bins", len(BIN_SPEC) - 2)   # drop the zero bin, as the interface expects
            _lo = _cg.createVariable("longitude", "f4", ("longitude",)); _lo.units = "degrees_east"; _lo[:] = longitude
            _la = _cg.createVariable("latitude", "f4", ("latitude",)); _la.units = "degrees_north"; _la[:] = latitude
            # time + valid_time: the web interface reads both. Match forecast2histogram exactly.
            _tm = _cg.createVariable("time", "f4", ("time",))
            _tm.units = "hours since 1900-01-01 00:00:00.0"; _tm.description = "Forecast model start time"
            _tm[:] = start_times[fcst_idx] if input_format != "operational" else start_times[0]
            _vt = _cg.createVariable("valid_time", "f4", ("valid_time",))
            _vt.units = "hours since 1900-01-01 00:00:00.0"; _vt.description = "Forecast prediction time"
            _vt[:] = np.array(valid_times_forecast).ravel()[valid_time_num]  # per-lead valid time
            _bn = _cg.createVariable("bins", "f4", ("bins",)); _bn.units = "mm/h"; _bn[:] = BIN_SPEC[1:-1]
            _ct = _cg.createVariable("counts", "i2", ("bins", "latitude", "longitude"), zlib=True, complevel=9)
            _ct.description = "Histogram bin counts"; _ct.num_members = int(_ens.shape[0])
            _ct[:] = _counts[1:, :, :]                        # drop zero bin
            _cg.close()
            print(f"wrote histogram counts -> {_cpath}", flush=True)

        # Score against RFE2 truth if it exists (always in eval/held-out; only when
        # available in operational -- a live forecast has no truth yet, so CRPS is skipped).
        if _have_truth:
            # log_precip=False: `pred` above has already been through denormalise(), so it
            # is mm/hr. Passing log_precip=True here returned truth as log10(1+y) and scored
            # log-space truth against linear-space members -- that is what made crps_run05
            # come out at 0.030 against run05's true 0.084 (evaluation.py denormalises both).
            truth_data, _ = load_truth_and_mask(d.strftime('%Y%m%d'), 0, log_precip=False, truth_path=truth_input_folder)
            print(f"shape truth = {np.shape(truth_data)}")
            print(f"shape ens_cgan_preds_stacked = {np.shape(ens_cgan_preds_stacked)}")
            crps = ps.crps_ensemble(
                truth_data,
                ens_cgan_preds_stacked,
                axis=0
            )
            netcdf_dict["crps"][0, valid_time_num, :, :] = crps
        else:
            print(f"no truth for {d:%Y%m%d} D+1 -> forecast/histogram only, CRPS skipped", flush=True)

    if not skip_this_date:   # these reference pred/gan_prediction, undefined if we skipped
        print("network_fcst_input finite:", np.isfinite(network_fcst_input).all())
        print("gan_prediction finite:", np.isfinite(gan_prediction).all())
        print("pred finite:", np.isfinite(pred).all())
        print("pred min/max:", np.nanmin(pred), np.nanmax(pred))
    netcdf_dict["rootgrp"].close()
    if skip_this_date and os.path.exists(nc_out_path):
        os.remove(nc_out_path)   # no valid forecast for this date -> drop the empty file

    # Close the ECMWF forecasts NetCDF file
    # nc_in.close()






