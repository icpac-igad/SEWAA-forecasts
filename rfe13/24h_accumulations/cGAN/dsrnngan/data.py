""" File for handling data loading and saving. """
import os
import datetime
import pickle

import numpy as np
import netCDF4 as nc
import xarray as xr

import read_config


data_paths = read_config.get_data_paths()
TRUTH_PATH = data_paths["GENERAL"]["TRUTH_PATH"]
FCST_PATH = data_paths["GENERAL"]["FORECAST_PATH"]
CONSTANTS_PATH = data_paths["GENERAL"]["CONSTANTS_PATH"]
NORMALISATION_PATH = data_paths["GENERAL"]["NORMALISATION_PATH"]

# Which lead time (Start of 24h accumulation period) are we using?
LEAD_IDX = data_paths["GENERAL"]["LEAD_IDX"]

# --- FIELD SET SELECTION ---------------------------------------------------------
# Every run so far needed this file hand-edited to switch input fields, which made
# re-evaluating an older checkpoint error-prone. Pick a set with the CGAN_FIELD_SET
# environment variable instead; the default reproduces run11.
#
#     CGAN_FIELD_SET=run06 python main.py --config config_run06.yaml --eval_full
#
# clim: 0 = none
#       1 = run09's single mm/day channel, indexed by the FORECAST date
#       2 = run11's mean+sd in mm/hr, indexed by the day being PREDICTED
#
# !! run06 and run11 BOTH come to 28 channels, by coincidence: 14 real fields vs
# !! 13 fields + 2 climatology channels. Loading one run's weights under the other's
# !! field set will NOT raise -- the shapes match -- it will silently produce garbage.
# !! That is why the resolved set is printed on import; check it before trusting a score.
_F13  = ['cp', 'mcc', 'sp', 'ssr', 't2m', 'tciw', 'tclw', 'tcrw', 'tcw', 'tcwv', 'tp', 'u700', 'v700']
_F14  = ['cape'] + _F13
_F4   = ['tp', 't2m', 'tcwv', 'sp']

FIELD_SETS = {
    # name       fields  accumulated            nonnegative                    clim
    'run05':    (_F4,    ['tp'],                ['tp', 'tcwv'],                0),
    'run06':    (_F14,   ['cp', 'ssr', 'tp'],   [f for f in _F14 if f not in ('u700', 'v700')], 0),
    'run07':    (_F14,   ['cp', 'ssr', 'tp'],   [f for f in _F14 if f not in ('u700', 'v700')], 0),
    'run08':    (_F13,   ['cp', 'ssr', 'tp'],   [f for f in _F13 if f not in ('u700', 'v700')], 0),
    'run09':    (_F13,   ['cp', 'ssr', 'tp'],   [f for f in _F13 if f not in ('u700', 'v700')], 1),
    'run10':    (_F13,   ['cp', 'ssr', 'tp'],   [f for f in _F13 if f not in ('u700', 'v700')], 0),
    'run11':    (_F13,   ['cp', 'ssr', 'tp'],   [f for f in _F13 if f not in ('u700', 'v700')], 2),
}

FIELD_SET = os.environ.get('CGAN_FIELD_SET', 'run11')
if FIELD_SET not in FIELD_SETS:
    raise ValueError(f"CGAN_FIELD_SET={FIELD_SET!r} unknown; pick one of {sorted(FIELD_SETS)}")

all_fcst_fields, accumulated_fields, nonnegative_fields, CLIM_CHANNELS = FIELD_SETS[FIELD_SET]

HOURS = 24  # daily RFE2 data

# --- RFE climatology predictor (run11): the 14th field, contributing TWO channels,
# the climatological MEAN and STANDARD DEVIATION for the day being predicted.
#
# This mirrors Oxford's ARC design, where 'IMERG' is an entry in all_fcst_fields and
# load_fcst reads {field}_mean / {field}_sd for it. It cannot go in all_fcst_fields
# here because load_fcst expects one file per YEAR indexed by [doy, valid_time, lat,
# lon], whereas the climatology is a single day-of-year file -- so it is appended in
# load_fcst_stack instead, giving the same 2*14 = 28 forecast channels.
#
# Source file is built by ~/Documentation/scripts/rfe2_make_climatology.py from RFE2
# 2001-2019 (validation year 2020 excluded), +/-15 days, in mm/hr.
#
# Both channels get log10(1+x), as tp/cp do (logprec), which keeps them O(1) without
# needing FCSTNorm entries -- normalisation is per-field, so adding this predictor
# does NOT require regenerating FCSTNorm2018.pkl.
#
# Changed from run09, which used ONE channel of mm/day climatology indexed by the
# FORECAST date. Here the index is the day being predicted (forecast + LEAD_IDX*HOURS),
# matching load_truth_and_mask, so the predictor describes the same day as the target.
USE_CLIMATOLOGY = True    # run11: 13 IFS fields + RFE climatology mean & sd
CLIM_CHANNELS = 2         # single source of truth; main.py + tfrecords_generator use this
_CLIM = None

def _load_climatology():
    global _CLIM
    if _CLIM is None:
        path = os.path.join(CONSTANTS_PATH, "RFE_climatology_meansd_doy.nc")
        with nc.Dataset(path) as d:
            _CLIM = (np.array(d["RFE_mean"][:]),    # (365, H, W), mm/hr
                     np.array(d["RFE_sd"][:]))      # (365, H, W), mm/hr
    return _CLIM

def climatology_channel(date_str, lead_days=0):
    """log-normalised RFE climatological mean+sd for the day being predicted, (H, W, 2).

    lead_days shifts the predicted day for multi-lead forecasts: 0 = D+1 (default, the
    validated lead), 1 = D+2, ... so the climatology predictor matches each forecast lead.
    """
    clim_mean, clim_sd = _load_climatology()
    fcst_date = datetime.datetime.strptime(date_str, "%Y%m%d")
    target = fcst_date + datetime.timedelta(hours=(int(LEAD_IDX) + int(lead_days)) * HOURS)
    m, dd = target.month, target.day
    if m == 2 and dd == 29:
        dd = 28
    doy = (datetime.date(2001, m, dd) - datetime.date(2001, 1, 1)).days   # 0..364
    out = np.stack([clim_mean[doy], clim_sd[doy]], axis=-1)
    return np.log10(1.0 + out).astype(np.float32)


# utility function; generator to iterate over a range of dates
def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days)):
        yield start_date + datetime.timedelta(days=n)


def denormalise(x):
    """
    Undo log-transform of rainfall.  Also cap at 100 (feel free to adjust according to application!)
    """
    return np.minimum(10**x - 1.0, 100.0)


def logprec(y, log_precip=False):
    if log_precip:
        return np.log10(1.0+y)
    else:
        return y


def get_dates(year,
              start_hour,
              end_hour):
    '''
    Returns list of valid forecast start dates for which RFE2 truth data
    exists. For each IFS forecast date D, truth is the RFE2 file for D+1.
    Dates are returned as a list of YYYYMMDD strings.

    Parameters:
        year (int): forecasts starting in this year
        start_hour (int): Lead time of first forecast desired
        end_hour (int): Lead time of last forecast desired
    '''
    assert year in (2018, 2019, 2020, 2021)
    assert start_hour >= 0
    assert end_hour <= 168
    assert start_hour % HOURS == 0
    assert end_hour % HOURS == 0
    assert end_hour >= start_hour

    start_date = datetime.date(year, 1, 1)
    end_date = datetime.date(year + 1, 1, 1)
    valid_dates = []

    for curdate in daterange(start_date, end_date):
        # truth file is the RFE2 accumulation for the day after the forecast date
        truth_date = curdate + datetime.timedelta(days=1)
        truth_path = os.path.join(TRUTH_PATH, str(truth_date.year),
                                  truth_date.strftime('%Y%m%d') + '.nc')
        if os.path.exists(truth_path):
            valid_dates.append(curdate.strftime('%Y%m%d'))

    return valid_dates


def load_truth_and_mask(date,
                        time_idx,
                        log_precip=False,
                        truth_path=None):
    '''
    Returns a single (truth, mask) item of RFE2 daily rainfall.

    RFE2 is now pre-regridded (by the downloader) onto the exact IFS / constants
    384x352 grid, so NO interpolation is needed here -- we read it directly.
    This keeps truth, forecast and constants registered cell-for-cell.

    Parameters:
        date: forecast start date (YYYYMMDD string)
        time_idx: unused for daily data, kept for API compatibility
        log_precip: whether to apply log10(1+x) transformation
    '''
    fcst_date = datetime.datetime.strptime(date, "%Y%m%d")
    truth_dt = fcst_date + datetime.timedelta(hours=int(LEAD_IDX) * HOURS)
    datestr = truth_dt.strftime('%Y%m%d')
    _truth_path = TRUTH_PATH if truth_path is None else truth_path
    data_path = os.path.join(_truth_path, str(truth_dt.year), f"{datestr}.nc")

    ds = xr.open_dataset(data_path)
    y = ds["precipitation"].values.squeeze()   # already (384, 352) on the IFS grid
    ds.close()

    y = np.where(np.isfinite(y), y, 0.0)        # ocean / missing -> 0
    y = np.maximum(y, 0.0)                       # clip tiny negatives from processing
    y = y / 24.0                                 # mm/day -> mm/hr to match IFS tp units

    mask = np.full(y.shape, False, dtype=bool)   # all valid; boundary handled at eval

    if log_precip:
        return np.log10(1 + y), mask
    else:
        return y, mask


def load_hires_constants(batch_size=1, constants_path=None):
    _constants_path = CONSTANTS_PATH if constants_path is None else constants_path
    oro_path = os.path.join(_constants_path, "elev.nc")
    df = xr.load_dataset(oro_path)
    # Orography in m.  Divide by 10,000 to give O(1) normalisation
    z = df["elevation"].values
    z /= 10000.0
    df.close()

    lsm_path = os.path.join(_constants_path, "lsm.nc")
    df = xr.load_dataset(lsm_path)
    # LSM is already 0:1
    lsm = df["lsm"].values
    df.close()

    temp = np.stack([z, lsm], axis=-1)  # shape H x W x 2
    return np.repeat(temp[np.newaxis, ...], batch_size, axis=0)  # shape batch_size x H x W x 2


def load_fcst_truth_batch(dates_batch,
                          time_idx_batch,
                          fcst_fields=all_fcst_fields,
                          log_precip=False,
                          norm=False):
    '''
    Returns a batch of (forecast, truth, mask) data, although usually the batch size is 1
    Parameters:
        dates_batch (iterable of strings): Dates of forecasts
        time_idx_batch (iterable of ints): Corresponding 'valid_time' array indices
        fcst_fields (list of strings): The fields to be used
        log_precip (bool): Whether to apply log10(1+x) transform to precip-related forecast fields, and truth
        norm (bool): Whether to apply normalisation to forecast fields to make O(1)
    '''
    batch_x = []  # forecast
    batch_y = []  # truth
    batch_mask = []  # mask

    for time_idx, date in zip(time_idx_batch, dates_batch):
        batch_x.append(load_fcst_stack(fcst_fields, date, time_idx, log_precip=log_precip, norm=norm))
        truth, mask = load_truth_and_mask(date, time_idx, log_precip=log_precip)
        batch_y.append(truth)
        batch_mask.append(mask)

    return np.array(batch_x), np.array(batch_y), np.array(batch_mask)


def load_fcst(field,
              date,
              time_idx,
              log_precip=False,
              norm=False,
              fcst_path=None,
              fcst_norm_dict=None,
              lead_idx=None):
    '''
    Returns forecast field data for the given date and time interval.

    Four channels are returned for each field:
        - instantaneous fields: mean and stdev at the start of the interval, mean and stdev at the end of the interval
        - accumulated field: mean and stdev of increment over the interval, and the last two channels are all 0
    '''

    # print(f"Loading forecast {field} on {date}")

    # First index in the lead time. Defaults to the configured D+1 (LEAD_IDX); callers
    # can pass lead_idx=1+4*L to read the L-th 24h lead (D+1+L) for multi-lead scoring.
    if lead_idx is None:
        lead_idx = LEAD_IDX

    # Allow the forecast folder and normalisation dict to be overridden
    # (e.g. from forecast.yaml); fall back to the module-level defaults.
    _fcst_path = FCST_PATH if fcst_path is None else fcst_path
    _fcst_norm = fcst_norm if fcst_norm_dict is None else fcst_norm_dict

    yearstr = date[:4]
    year = int(yearstr)
    ds_path = os.path.join(_fcst_path, yearstr, f"{field}.nc")

    # open using netCDF
    nc_file = nc.Dataset(ds_path, mode="r")
    all_data_mean = nc_file[f"{field}_mean"]
    all_data_sd = nc_file[f"{field}_sd"]
    # data is stored as [day of year, valid time index, lat, lon]

    # Locate this date on the file's OWN time axis. The old code assumed
    #   fcst_idx = day-of-year (Jan 1 = 0)
    # which is correct only for files that start on Jan 1 (the 2018-2021 full-year
    # training files). Partial-year files like 2023/2024 start on Jun 1, so
    # day-of-year read the WRONG day (Jun 1 -> index 151 -> Oct 30). Matching the
    # date against the time variable is correct for both; for full-year files it
    # returns the same index as before, so training/eval are unchanged.
    fcst_date = datetime.datetime.strptime(date, "%Y%m%d").date()
    _ftimes = nc.num2date(nc_file["time"][:], nc_file["time"].units)
    _want = fcst_date.strftime("%Y%m%d")
    _matches = [i for i, x in enumerate(_ftimes) if x.strftime("%Y%m%d") == _want]
    if not _matches:
        nc_file.close()
        raise ValueError(f"date {date} not present in {ds_path}")
    fcst_idx = _matches[0]

    if field in accumulated_fields:
        # return mean, sd, 0, 0.  zero fields are so that each field returns a 4 x ny x nx array.
        # accumulated fields have been pre-processed s.t. data[:, j, :, :] has accumulation between times j and j+1
        data1 = np.mean(all_data_mean[fcst_idx, lead_idx:lead_idx+4, :, :], axis=0)            # Mean of the accumulations
        data2 = np.sqrt(np.mean(all_data_sd[fcst_idx, lead_idx:lead_idx+4, :, :]**2, axis=0))  # RMS of the standard deviations
        data = np.stack([data1, data2], axis=-1)
    else:
        # return mean and std computed using the trapezium rule
        temp_data_mean = all_data_mean[fcst_idx, lead_idx:lead_idx+5, :, :]
        temp_data_var = all_data_sd[fcst_idx, lead_idx:lead_idx+5, :, :]**2  # Convert to variances
        data1 = (temp_data_mean[0, :, :]/2 + np.sum(temp_data_mean[1:4,:,:], axis=0) + temp_data_mean[4,:,:]/2)/4
        data2 = (temp_data_var[0, :, :]/2 + np.sum(temp_data_var[1:4,:,:], axis=0) + temp_data_var[4,:,:]/2)/4
        data = np.stack([data1, np.sqrt(data2)], axis=-1)

    nc_file.close()

    if field in nonnegative_fields:
        data = np.maximum(data, 0.0)  # eliminate any data weirdness/regridding issues

    if field in ["tp", "cp"]:
        # precip is measured in metres, so multiply to get mm
        data *= 1000
        data /= HOURS  # convert to mm/hr
    elif field in accumulated_fields:
        # for all other accumulated fields [just ssr for us]
        data /= (HOURS*3600)  # convert from a 6-hr difference to a per-second rate

    if field in ["tp", "cp"] and log_precip:
        return logprec(data, log_precip)
    elif norm:
        # apply transformation to make fields O(1), based on historical
        # forecast data from one of the training years
        if _fcst_norm is None:
            raise RuntimeError("Forecast normalisation dictionary has not been loaded")
        if field in ["mcc"]:
            # already 0-1
            return data
        elif field in ["sp", "t2m"]:
            # these are bounded well away from zero, so subtract mean from ens mean (but NOT from ens sd!)
            data[:, :, 0] -= _fcst_norm[field]["mean"]
            return data/_fcst_norm[field]["std"]
        elif field in nonnegative_fields:
            return data/_fcst_norm[field]["max"]
        else:
            # winds
            return data/max(-_fcst_norm[field]["min"], _fcst_norm[field]["max"])
    else:
        return data


def load_fcst_operational(field, ifs_nc, valid_time_num=0, log_precip=False,
                          norm=False, fcst_norm_dict=None):
    """One field from an OPERATIONAL IFS file (IFS_<date>_00Z.nc) -> (H, W, 2).

    Bridges the operational per-day format (the live gbmc -> Oxford feed) to the model.
    It mirrors load_fcst EXACTLY -- same accumulation window, unit conversion and
    per-field normalisation -- but reads {field}_ensemble_mean /
    {field}_ensemble_standard_deviation (shape [valid_time, lat, lon]) from an already-open
    netCDF handle instead of the per-field yearly training file.

    valid_time_num=0 selects the same 1:5 (accumulated) / 1:6 (trapezium) window that
    training load_fcst reads at LEAD_IDX=1 -- the D+1 forecast run11 was trained on -- so
    inputs are on exactly the training scale.
    """
    _fcst_norm = fcst_norm if fcst_norm_dict is None else fcst_norm_dict
    m = ifs_nc[f"{field}_ensemble_mean"]
    s = ifs_nc[f"{field}_ensemble_standard_deviation"]
    b = valid_time_num * 4 + 1
    if field in accumulated_fields:
        data1 = np.mean(m[b:b + 4, :, :], axis=0)
        data2 = np.sqrt(np.mean(s[b:b + 4, :, :] ** 2, axis=0))
        data = np.stack([data1, data2], axis=-1)
    else:
        tm = m[b:b + 5, :, :]
        tv = s[b:b + 5, :, :] ** 2
        data1 = (tm[0] / 2 + np.sum(tm[1:4], axis=0) + tm[4] / 2) / 4
        data2 = (tv[0] / 2 + np.sum(tv[1:4], axis=0) + tv[4] / 2) / 4
        data = np.stack([data1, np.sqrt(data2)], axis=-1)

    # ---- identical to load_fcst from here: units + normalisation ----
    if field in nonnegative_fields:
        data = np.maximum(data, 0.0)
    if field in ["tp", "cp"]:
        data = data * 1000.0
        data = data / HOURS
    elif field in accumulated_fields:
        data = data / (HOURS * 3600)

    if field in ["tp", "cp"] and log_precip:
        return logprec(data, log_precip)
    elif norm:
        if _fcst_norm is None:
            raise RuntimeError("Forecast normalisation dictionary has not been loaded")
        if field in ["mcc"]:
            return data
        elif field in ["sp", "t2m"]:
            data[:, :, 0] -= _fcst_norm[field]["mean"]
            return data / _fcst_norm[field]["std"]
        elif field in nonnegative_fields:
            return data / _fcst_norm[field]["max"]
        else:
            return data / max(-_fcst_norm[field]["min"], _fcst_norm[field]["max"])
    else:
        return data


def load_fcst_stack(fields,
                    date,
                    time_idx,
                    log_precip=False,
                    norm=False):
    '''
    Returns forecast fields, for the given date and time interval.
    Each field returned by load_fcst has two channels (see load_fcst for details),
    then these are concatentated to form an array of H x W x 4*len(fields)
    '''
    field_arrays = []
    for f in fields:
        field_arrays.append(load_fcst(f, date, time_idx, log_precip=log_precip, norm=norm))
    stack = np.concatenate(field_arrays, axis=-1)
    if USE_CLIMATOLOGY:
        stack = np.concatenate([stack, climatology_channel(date)], axis=-1)  # +CLIM_CHANNELS
    return stack


def sanitise_fcst_input(x, fields, date_str, clim_channels=0):
    """Make a forecast input array safe to feed the model, and decide if it is usable.

    IFS files occasionally ship a corrupt field -- e.g. 2024-01-28 had all-NaN u700/v700
    in the 2024 archive. A single NaN channel propagates through the network and poisons
    the whole prediction (and any running CRPS mean). In an operational setting we must
    never silently emit a NaN forecast, and never crash: we either recover or skip with a
    clear reason.

    Policy:
      * finite input            -> returned unchanged, usable=True.
      * some fields NaN/Inf     -> non-finite values replaced with 0.0 (the field mean in
                                   normalised space -- the least-surprising fill, so the
                                   model leans on the good fields), usable=True, and the
                                   affected fields are reported.
      * the precip field `tp` dead, OR more than a third of the IFS fields dead
                                -> unusable=... the caller should SKIP this date rather
                                   than trust a forecast built mostly from filled channels.

    Each IFS field occupies 2 channels (mean, sd); trailing `clim_channels` are the
    climatology append (checked but never counted as an IFS field).

    Returns (clean_array, usable: bool, report: dict).
    """
    x = np.asarray(x)
    bad = ~np.isfinite(x)
    n_ifs = len(fields)
    report = {"date": date_str, "dead_fields": [], "nan_fraction": float(bad.mean())}
    if not bad.any():
        return x, True, report

    # which named IFS fields are affected, and how badly (2 channels each)
    dead = []
    for i, f in enumerate(fields):
        seg = bad[..., 2 * i:2 * i + 2]
        frac = float(seg.mean())
        if frac > 0:
            report["dead_fields"].append((f, round(frac, 3)))
            if frac > 0.9:                      # essentially the whole field is gone
                dead.append(f)
    if clim_channels and bad[..., -clim_channels:].any():
        report["dead_fields"].append(("climatology", 1.0))
        dead.append("climatology")

    clean = np.where(bad, 0.0, x).astype(np.float32)

    critical = ("tp" in dead) or ("climatology" in dead) or (len(dead) > n_ifs / 3)
    report["skipped"] = bool(critical)
    return clean, (not critical), report


def get_fcst_stats_slow(field, year=2018):
    '''
    Calculates and returns min, max, mean, std per field,
    which can be used to generate normalisation parameters.

    These are done via the data loading routines, which is
    slightly inefficient.
    '''
    dates = get_dates(year, start_hour=0, end_hour=24)

    mi = 0.0
    mx = 0.0
    dsum = 0.0
    dsqrsum = 0.0
    nsamples = 0
    for datestr in dates:
        for time_idx in range(28):
            data = load_fcst(field, datestr, time_idx)[:, :, 0]
            mi = min(mi, data.min())
            mx = max(mx, data.max())
            dsum += np.mean(data)
            dsqrsum += np.mean(np.square(data))
            nsamples += 1
    mn = dsum / nsamples
    sd = (dsqrsum/nsamples - mn**2)**0.5
    return mi, mx, mn, sd


def get_fcst_stats_fast(field, year=2018):
    '''
    Calculates and returns min, max, mean, std per field,
    which can be used to generate normalisation parameters.

    These are done directly from the forecast netcdf file,
    which is somewhat faster, as long as it fits into memory.
    '''
    ds_path = os.path.join(FCST_PATH, str(year), f"{field}.nc")
    nc_file = nc.Dataset(ds_path, mode="r")

    if field in accumulated_fields:
        data = nc_file[f"{field}_mean"][:, :-1, :, :]  # last time_idx is full of zeros
    else:
        data = nc_file[f"{field}_mean"][:, :, :, :]

    nc_file.close()

    if field in ["tp", "cp"]:
        # precip is measured in metres, so multiply to get mm
        data *= 1000
        data /= HOURS  # convert to mm/hr
        data = np.maximum(data, 0.0)  # shouldn't be necessary, but just in case
    elif field in accumulated_fields:
        # for all other accumulated fields [just ssr for us]
        data /= (HOURS*3600)  # convert from a 6-hr difference to a per-second rate

    mi = data.min()
    mx = data.max()
    mn = np.mean(data, dtype=np.float64)
    sd = np.std(data, dtype=np.float64)
    return mi, mx, mn, sd


def gen_fcst_norm(year=2018):
    '''
    One-off function, used to generate normalisation constants, which
    are used to normalise the various input fields for training/inference.
    '''

    stats_dic = {}
    fcstnorm_path = os.path.join(NORMALISATION_PATH, f"FCSTNorm{year}.pkl")

    # make sure we can actually write there, before doing computation!!!
    with open(fcstnorm_path, 'wb') as f:
        pickle.dump(stats_dic, f)

    for field in all_fcst_fields:
        print(field)
        mi, mx, mn, sd = get_fcst_stats_fast(field, year)
        stats_dic[field] = {}
        stats_dic[field]['min'] = mi
        stats_dic[field]['max'] = mx
        stats_dic[field]['mean'] = mn
        stats_dic[field]['std'] = sd

    with open(fcstnorm_path, 'wb') as f:
        pickle.dump(stats_dic, f)


def load_fcst_norm(year=2018, normalisation_path=None):
    print("In load_fcst_norm")
    _norm_path = NORMALISATION_PATH if normalisation_path is None else normalisation_path
    fcstnorm_path = os.path.join(_norm_path, f"FCSTNorm{year}.pkl")
    print(f"fcstnorm_path = {fcstnorm_path}")
    with open(fcstnorm_path, 'rb') as f:
        return pickle.load(f)


try:
    print("Loading forecast normalisations")
    fcst_norm = load_fcst_norm(2018)
except:  # noqa
    fcst_norm = None
    print("******************************************")
    print("*** FORECAST NORMALISATIONS NOT LOADED ***")
    print("******************************************")
