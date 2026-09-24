"""Unified data loading for all datasets (IMERG, CHIRPS, RFE).

Dataset behaviour is driven by the CGAN_DATASET and CGAN_FIELD_SET
environment variables. See dataset_config.py for the registry.
"""
import os
import sys
import datetime
import pickle

import numpy as np
import netCDF4 as nc
import xarray as xr

import read_config

# ── Allow importing dataset_config from the project root ─────────────────────
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
import dataset_config  # noqa: E402

# ── Data paths from read_config (data_paths.yaml + local_config.yaml) ────────
data_paths = read_config.get_data_paths()
TRUTH_PATH = data_paths["GENERAL"]["TRUTH_PATH"]
FCST_PATH = data_paths["GENERAL"]["FORECAST_PATH"]
CONSTANTS_PATH = data_paths["GENERAL"]["CONSTANTS_PATH"]
NORMALISATION_PATH = data_paths["GENERAL"]["NORMALISATION_PATH"]
LEAD_IDX = data_paths["GENERAL"]["LEAD_IDX"]

# ── Dataset configuration ────────────────────────────────────────────────────
_DATASET_NAME = dataset_config.get_active_dataset_name()
_DATASET_CFG = dataset_config.get_active_dataset()

# Override CONSTANTS_PATH and NORMALISATION_PATH with dataset-specific directories
# when they exist. data_paths.yaml always points to the shared IMERG constants/norm;
# CHIRPS and RFE have their own under datasets/<name>/.
_ds_constants = os.path.join(_PROJECT_ROOT, _DATASET_CFG["data_root"], "cGAN_data")
if os.path.isdir(_ds_constants):
    CONSTANTS_PATH = _ds_constants
_ds_norm = os.path.join(_PROJECT_ROOT, _DATASET_CFG["data_root"], "24h")
if os.path.isdir(_ds_norm):
    NORMALISATION_PATH = _ds_norm

# ── Field set selection ──────────────────────────────────────────────────────
_F13 = ['cp', 'mcc', 'sp', 'ssr', 't2m', 'tciw', 'tclw', 'tcrw', 'tcw', 'tcwv', 'tp', 'u700', 'v700']
_F14_CAPE = ['cape'] + _F13
_F14_CLIM = ['climatology'] + _F13
_F4 = ['tp', 't2m', 'tcwv', 'sp']

FIELD_SETS = {
    # ── IMERG ──
    'imerg_24h':  (_F13,      ['cp', 'ssr', 'tp'], [f for f in _F13 if f not in ('u700', 'v700')], 0),
    # ── CHIRPS ──
    'run07':      (_F14_CLIM, ['cp', 'ssr', 'tp'], ['climatology'] + [f for f in _F13 if f not in ('u700', 'v700')], 0),
    # ── RFE ──
    'run05':      (_F4,       ['tp'],              ['tp', 'tcwv'],                                  0),
    'run06':      (_F14_CAPE, ['cp', 'ssr', 'tp'], [f for f in _F14_CAPE if f not in ('u700', 'v700')], 0),
    'run08':      (_F13,      ['cp', 'ssr', 'tp'], [f for f in _F13 if f not in ('u700', 'v700')], 0),
    'run09':      (_F13,      ['cp', 'ssr', 'tp'], [f for f in _F13 if f not in ('u700', 'v700')], 1),
    'run10':      (_F13,      ['cp', 'ssr', 'tp'], [f for f in _F13 if f not in ('u700', 'v700')], 0),
    'run11':      (_F13,      ['cp', 'ssr', 'tp'], [f for f in _F13 if f not in ('u700', 'v700')], 2),
}

# Resolve the active field set
_default_fs = _DATASET_CFG.get("default_field_set_24h", "imerg_24h")
FIELD_SET = os.environ.get('CGAN_FIELD_SET', _default_fs)
if FIELD_SET not in FIELD_SETS:
    raise ValueError(f"CGAN_FIELD_SET={FIELD_SET!r} unknown; pick one of {sorted(FIELD_SETS)}")

all_fcst_fields, accumulated_fields, nonnegative_fields, CLIM_CHANNELS = FIELD_SETS[FIELD_SET]
print(f"[data.py] dataset={_DATASET_NAME}, field_set={FIELD_SET}, "
      f"fields={len(all_fcst_fields)}, clim_channels={CLIM_CHANNELS}")

HOURS = 24

# ── Truth loading behaviour (from dataset config) ────────────────────────────
_TRUTH_NAN_TO_ZERO = _DATASET_CFG.get("truth_nan_to_zero", False)
_TRUTH_UNIT_CONV = _DATASET_CFG.get("truth_unit_conversion", 1.0)

# ── Climatology (RFE run11+) ─────────────────────────────────────────────────
USE_CLIMATOLOGY = CLIM_CHANNELS > 0
_CLIM = None


def _load_climatology(constants_path=None):
    global _CLIM
    if _CLIM is None:
        _cpath = CONSTANTS_PATH if constants_path is None else constants_path
        path = os.path.join(_cpath, "RFE_climatology_meansd_doy.nc")
        try:
            with nc.Dataset(path) as d:
                _CLIM = (np.array(d["RFE_mean"][:]),
                         np.array(d["RFE_sd"][:]))
        except (FileNotFoundError, OSError) as e:
            print(f"WARNING: RFE climatology unavailable ({e}); "
                  f"using zero-fill placeholder for the {CLIM_CHANNELS} climatology channel(s).")
            _CLIM = "missing"
    return _CLIM


def climatology_channel(date_str, lead_days=0, constants_path=None):
    """Log-normalised climatological mean+sd for the predicted day, shape (H, W, 2)."""
    clim = _load_climatology(constants_path=constants_path)
    if clim == "missing":
        raise FileNotFoundError("RFE_climatology_meansd_doy.nc not available")
    clim_mean, clim_sd = clim
    fcst_date = datetime.datetime.strptime(date_str, "%Y%m%d")
    target = fcst_date + datetime.timedelta(hours=(int(LEAD_IDX) + int(lead_days)) * HOURS)
    m, dd = target.month, target.day
    if m == 2 and dd == 29:
        dd = 28
    doy = (datetime.date(2001, m, dd) - datetime.date(2001, 1, 1)).days
    out = np.stack([clim_mean[doy], clim_sd[doy]], axis=-1)
    return np.log10(1.0 + out).astype(np.float32)


# ── Utility functions ─────────────────────────────────────────────────────────

def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days)):
        yield start_date + datetime.timedelta(days=n)


def denormalise(x):
    return np.minimum(10**x - 1.0, 100.0)


def logprec(y, log_precip=False):
    if log_precip:
        return np.log10(1.0 + y)
    else:
        return y


# ── Date discovery ────────────────────────────────────────────────────────────

def get_dates(year, start_hour, end_hour):
    """Valid forecast start dates for which truth data exists."""
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
        truth_date = curdate + datetime.timedelta(days=1)
        truth_path = os.path.join(TRUTH_PATH, str(truth_date.year),
                                  truth_date.strftime('%Y%m%d') + '.nc')
        if os.path.exists(truth_path):
            valid_dates.append(curdate.strftime('%Y%m%d'))

    return valid_dates


# ── Truth loading ─────────────────────────────────────────────────────────────

def load_truth_and_mask(date, time_idx, log_precip=False, truth_path=None):
    """Load truth precipitation for the predicted day.

    Handles IMERG, CHIRPS, and RFE truth formats via dataset_config flags:
    - truth_nan_to_zero: replace NaN/ocean with 0
    - truth_unit_conversion: multiply by this factor (e.g. 1/24 for mm/day→mm/hr)
    """
    fcst_date = datetime.datetime.strptime(date, "%Y%m%d")
    truth_dt = fcst_date + datetime.timedelta(hours=int(LEAD_IDX) * HOURS)
    datestr = truth_dt.strftime('%Y%m%d')
    _truth_path = TRUTH_PATH if truth_path is None else truth_path
    data_path = os.path.join(_truth_path, str(truth_dt.year), f"{datestr}.nc")

    ds = xr.open_dataset(data_path)
    y = ds["precipitation"].values.squeeze()
    ds.close()

    if _TRUTH_NAN_TO_ZERO:
        y = np.where(np.isfinite(y), y, 0.0)
        y = np.maximum(y, 0.0)

    if _TRUTH_UNIT_CONV != 1.0:
        y = y * _TRUTH_UNIT_CONV

    mask = np.full(y.shape, False, dtype=bool)

    if log_precip:
        return np.log10(1 + y), mask
    else:
        return y, mask


# ── Constants loading ─────────────────────────────────────────────────────────

def load_hires_constants(batch_size=1, constants_path=None):
    _constants_path = CONSTANTS_PATH if constants_path is None else constants_path
    oro_path = os.path.join(_constants_path, "elev.nc")
    df = xr.load_dataset(oro_path)
    z = df["elevation"].values
    z /= 10000.0
    df.close()

    lsm_path = os.path.join(_constants_path, "lsm.nc")
    df = xr.load_dataset(lsm_path)
    lsm = df["lsm"].values
    df.close()

    temp = np.stack([z, lsm], axis=-1)
    return np.repeat(temp[np.newaxis, ...], batch_size, axis=0)


# ── Forecast loading ─────────────────────────────────────────────────────────

def load_fcst_truth_batch(dates_batch, time_idx_batch, fcst_fields=None,
                          log_precip=False, norm=False):
    if fcst_fields is None:
        fcst_fields = all_fcst_fields
    batch_x, batch_y, batch_mask = [], [], []
    for time_idx, date in zip(time_idx_batch, dates_batch):
        batch_x.append(load_fcst_stack(fcst_fields, date, time_idx, log_precip=log_precip, norm=norm))
        truth, mask = load_truth_and_mask(date, time_idx, log_precip=log_precip)
        batch_y.append(truth)
        batch_mask.append(mask)
    return np.array(batch_x), np.array(batch_y), np.array(batch_mask)


def load_fcst(field, date, time_idx, log_precip=False, norm=False,
              fcst_path=None, fcst_norm_dict=None, lead_idx=None):
    """Load one IFS forecast field → (H, W, 2) array [mean, sd]."""
    if lead_idx is None:
        lead_idx = LEAD_IDX

    _fcst_path = FCST_PATH if fcst_path is None else fcst_path
    _fcst_norm = fcst_norm if fcst_norm_dict is None else fcst_norm_dict

    yearstr = date[:4]
    ds_path = os.path.join(_fcst_path, yearstr, f"{field}.nc")

    nc_file = nc.Dataset(ds_path, mode="r")
    all_data_mean = nc_file[f"{field}_mean"]
    all_data_sd = nc_file[f"{field}_sd"]

    # Locate this date on the file's time axis (handles partial-year files)
    fcst_date = datetime.datetime.strptime(date, "%Y%m%d").date()
    _ftimes = nc.num2date(nc_file["time"][:], nc_file["time"].units)
    _want = fcst_date.strftime("%Y%m%d")
    _matches = [i for i, x in enumerate(_ftimes) if x.strftime("%Y%m%d") == _want]
    if not _matches:
        nc_file.close()
        raise ValueError(f"date {date} not present in {ds_path}")
    fcst_idx = _matches[0]

    if field in accumulated_fields:
        data1 = np.mean(all_data_mean[fcst_idx, lead_idx:lead_idx + 4, :, :], axis=0)
        data2 = np.sqrt(np.mean(all_data_sd[fcst_idx, lead_idx:lead_idx + 4, :, :] ** 2, axis=0))
        data = np.stack([data1, data2], axis=-1)
    else:
        tm = all_data_mean[fcst_idx, lead_idx:lead_idx + 5, :, :]
        tv = all_data_sd[fcst_idx, lead_idx:lead_idx + 5, :, :] ** 2
        data1 = (tm[0, :, :] / 2 + np.sum(tm[1:4, :, :], axis=0) + tm[4, :, :] / 2) / 4
        data2 = (tv[0, :, :] / 2 + np.sum(tv[1:4, :, :], axis=0) + tv[4, :, :] / 2) / 4
        data = np.stack([data1, np.sqrt(data2)], axis=-1)

    nc_file.close()

    if field in nonnegative_fields:
        data = np.maximum(data, 0.0)

    if field in ["tp", "cp"]:
        data *= 1000
        data /= HOURS
    elif field in accumulated_fields:
        data /= (HOURS * 3600)

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


def load_fcst_operational(field, ifs_nc, valid_time_num=0, log_precip=False,
                          norm=False, fcst_norm_dict=None):
    """One field from an OPERATIONAL IFS file (IFS_<date>_00Z.nc) → (H, W, 2)."""
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


def load_fcst_stack(fields, date, time_idx, log_precip=False, norm=False):
    """Forecast fields concatenated → (H, W, 2*len(fields) [+ clim_channels])."""
    field_arrays = []
    for f in fields:
        field_arrays.append(load_fcst(f, date, time_idx, log_precip=log_precip, norm=norm))
    stack = np.concatenate(field_arrays, axis=-1)
    if USE_CLIMATOLOGY:
        try:
            stack = np.concatenate([stack, climatology_channel(date)], axis=-1)
        except (FileNotFoundError, OSError):
            stack = np.concatenate(
                [stack, np.zeros(stack.shape[:-1] + (CLIM_CHANNELS,), dtype=np.float32)],
                axis=-1)
    return stack


def sanitise_fcst_input(x, fields, date_str, clim_channels=0):
    """Make a forecast input array safe to feed the model.

    Returns (clean_array, usable: bool, report: dict).
    """
    x = np.asarray(x)
    bad = ~np.isfinite(x)
    n_ifs = len(fields)
    report = {"date": date_str, "dead_fields": [], "nan_fraction": float(bad.mean())}
    if not bad.any():
        return x, True, report

    dead = []
    for i, f in enumerate(fields):
        seg = bad[..., 2 * i:2 * i + 2]
        frac = float(seg.mean())
        if frac > 0:
            report["dead_fields"].append((f, round(frac, 3)))
            if frac > 0.9:
                dead.append(f)
    if clim_channels and bad[..., -clim_channels:].any():
        report["dead_fields"].append(("climatology", 1.0))
        dead.append("climatology")

    clean = np.where(bad, 0.0, x).astype(np.float32)
    critical = ("tp" in dead) or ("climatology" in dead) or (len(dead) > n_ifs / 3)
    report["skipped"] = bool(critical)
    return clean, (not critical), report


# ── Normalisation stats ──────────────────────────────────────────────────────

def get_fcst_stats_slow(field, year=2018):
    dates = get_dates(year, start_hour=0, end_hour=24)
    mi, mx, dsum, dsqrsum, nsamples = 0.0, 0.0, 0.0, 0.0, 0
    for datestr in dates:
        for time_idx in range(28):
            data = load_fcst(field, datestr, time_idx)[:, :, 0]
            mi = min(mi, data.min())
            mx = max(mx, data.max())
            dsum += np.mean(data)
            dsqrsum += np.mean(np.square(data))
            nsamples += 1
    mn = dsum / nsamples
    sd = (dsqrsum / nsamples - mn ** 2) ** 0.5
    return mi, mx, mn, sd


def get_fcst_stats_fast(field, year=2018):
    ds_path = os.path.join(FCST_PATH, str(year), f"{field}.nc")
    nc_file = nc.Dataset(ds_path, mode="r")
    if field in accumulated_fields:
        data = nc_file[f"{field}_mean"][:, :-1, :, :]
    else:
        data = nc_file[f"{field}_mean"][:, :, :, :]
    nc_file.close()
    if field in ["tp", "cp"]:
        data *= 1000
        data /= HOURS
        data = np.maximum(data, 0.0)
    elif field in accumulated_fields:
        data /= (HOURS * 3600)
    return data.min(), data.max(), np.mean(data, dtype=np.float64), np.std(data, dtype=np.float64)


def gen_fcst_norm(year=2018):
    stats_dic = {}
    fcstnorm_path = os.path.join(NORMALISATION_PATH, f"FCSTNorm{year}.pkl")
    with open(fcstnorm_path, 'wb') as f:
        pickle.dump(stats_dic, f)
    for field in all_fcst_fields:
        print(field)
        mi, mx, mn, sd = get_fcst_stats_fast(field, year)
        stats_dic[field] = {'min': mi, 'max': mx, 'mean': mn, 'std': sd}
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
except Exception:
    fcst_norm = None
    print("******************************************")
    print("*** FORECAST NORMALISATIONS NOT LOADED ***")
    print("******************************************")
