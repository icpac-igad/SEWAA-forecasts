#!/usr/bin/env python
"""Unified operational forecast runner for all datasets.

Dataset selection via CGAN_DATASET environment variable (default: imerg).
Supports IMERG (6h + 24h), CHIRPS (24h), RFE (24h). IFS input data is fetched
over HTTP from the Oxford archive, falling back to megacorr.dynu.net.

    CGAN_DATASET=imerg python run_forecast.py --accumulation 24h --date 20260920
    CGAN_DATASET=chirps python run_forecast.py --date 20260920
    CGAN_DATASET=rfe python run_forecast.py --date 20260920
"""
import argparse
import os
import sys
import subprocess
import pathlib
import platform
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dataset_config import get_active_dataset, get_active_dataset_name  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
DATASET_NAME = get_active_dataset_name()
DATASET_CFG = get_active_dataset()

VALID_HOURS_6H = [30, 36, 42, 48]
VALID_HOURS_24H = [6, 30, 54, 78, 102, 126, 150]

# Dataset-specific field set env var values
_FIELD_SET_ENV = {
    "imerg": "imerg_24h",
    "chirps": "run07",
    "rfe": "run11",
}


# A partial/interrupted download leaves a file that exists but won't open; check_counts_files
# and the caller only look at os.path.isfile(), so a corrupt file blocks that date's forecast
# forever unless removed here so it gets re-downloaded.
def is_valid_netcdf(path):
    try:
        import xarray as xr
        xr.open_dataset(path).close()
        return True
    except Exception:
        return False


# forecast_date.py's output file defines its dimensions up front (create_output_file) and
# only fills the unlimited time/valid_time record axis as each lead time finishes. If the
# process is killed partway (OOM is common at ensemble_members: 1000 -- see forecast.yaml)
# the file is left behind opening fine but with zero (or fewer than expected) valid_time
# records, which then crashes forecast2histogram*.py and find_available_dates.py downstream.
# A bare os.path.isfile() check can't tell a genuinely complete forecast from this, and would
# skip regenerating it forever -- so check the actual record count instead.
def has_forecast_output(path, min_valid_times=1):
    try:
        import netCDF4 as nc
        with nc.Dataset(path) as d:
            return d.dimensions["valid_time"].size >= min_valid_times
    except Exception:
        return False


# Parse arguments to this script
def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--accumulation", default=None,
                   help="Accumulation window: 6h or 24h")
    p.add_argument("--date", default=None,
                   help="Init date YYYYMMDD (default: yesterday UTC)")
    p.add_argument("--time", default="0000",
                   help="Init time HHMM")
    p.add_argument("--delete_forecasts", default=None,
                   help="Delete raw ensemble after counts are computed (Y/N)")
    p.add_argument("--disable_ELR", nargs="*", default=None,
                   help="Disable ELR forecasts")
    return p.parse_args()


def resolve_args(args):
    supported = DATASET_CFG["accumulations"]
    default_accum = DATASET_CFG["default_accumulation"]

    if args.accumulation is not None:
        accum = args.accumulation.replace("h", "")
        if accum == "6":
            accumulation_time = 6
        elif accum == "24":
            accumulation_time = 24
        else:
            sys.exit(f"ERROR: unknown accumulation '{args.accumulation}'. Use 6h or 24h.")
        if f"{accumulation_time}h" not in supported:
            sys.exit(f"ERROR: {DATASET_NAME} only supports {supported} accumulations.")
    else:
        accumulation_time = int(default_accum.replace("h", ""))

    if args.date is not None:
        if len(args.date) != 8:
            sys.exit("ERROR: --date must be YYYYMMDD.")
        date_str = args.date
    else:
        date_str = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime("%Y%m%d")

    hour = int(args.time[:2]) if args.time else 0

    if accumulation_time == 6 and hour not in (0, 6, 12, 18):
        sys.exit("ERROR: 6h forecasts use times 0000, 0600, 1200, 1800.")
    if accumulation_time == 24 and hour != 0:
        sys.exit("ERROR: 24h forecasts initialise at 0000 only.")

    delete = str(args.delete_forecasts).lower() in ("t", "y") if args.delete_forecasts else False
    run_elr = args.disable_ELR is None

    return accumulation_time, date_str, hour, delete, run_elr


# ── IFS download ──────────────────────────────────────────────────────────────
# Mirrors to try in order, highest precedence first. All datasets 
# read from the same IFS archive, so a single HTTP fallback chain covers
# all of them without any per-dataset download configuration.
IFS_SOURCES = [
    ("University of Oxford",
     "https://rain.physics.ox.ac.uk/ICPAC/operational/{accum}h_accumulations/"
     "IFS_forecast_data/{year}/{fname}"),
    ("megacorr.dynu.net",
     "http://megacorr.dynu.net/ICPAC/SEWAA_forecasts/{accum}h_accumulations/"
     "IFS_forecast_data/{year}/{fname}"),
     ("ICPAC data portal",
     "https://icpac-data-portal-8979869085.europe-west1.run.app/cgan-data/"
     "{accum}h_accumulations/IFS_forecast_data/{year}/{fname}"),
]


def download_ifs_data(date_str, hour, accumulation_time, ifs_dir):
    """Fetch IFS forecast data, trying each mirror in IFS_SOURCES in turn.

    Exits the program if the file is unavailable from every known source.
    """
    pathlib.Path(ifs_dir).mkdir(exist_ok=True, parents=True)
    fname = f"IFS_{date_str}_{hour:02d}Z.nc"
    dst = os.path.join(ifs_dir, fname)

    if os.path.isfile(dst):
        if is_valid_netcdf(dst):
            print(f"{dst} already exists and is valid.")
            return dst
        print(f"{dst} exists but is corrupt/incomplete; re-downloading.")
        os.remove(dst)

    year = date_str[:4]
    oblivion = "nul" if platform.system() == "Windows" else "/dev/null"

    for name, url_template in IFS_SOURCES:
        url = url_template.format(accum=accumulation_time, year=year, fname=fname)
        print(f"Checking {name} for {fname}")
        r = subprocess.run(["curl", "-Isw", "%{http_code}", url, "-o", oblivion],
                           capture_output=True, text=True)
        if r.stdout.strip().endswith("200"):
            print(f"Downloading {fname} from {name} -> {ifs_dir}/")
            subprocess.run(["curl", "-fL", "--retry", "20", "--retry-delay", "5",
                            "-C", "-", url, "-o", dst])
            return dst
        print(f"{fname} not available from {name} (HTTP {r.stdout.strip()}).")

    sources = ", ".join(name for name, _ in IFS_SOURCES)
    sys.exit(f"ERROR: {fname} is not available from any known source ({sources}).")


# ── Counts checking ──────────────────────────────────────────────────────────

def check_counts_files(counts_path, date_str, hour, valid_hours):
    year = date_str[:4]
    return all(
        os.path.isfile(os.path.join(counts_path, year, f"counts_{date_str}_{hour:02d}_{h}h.nc"))
        for h in valid_hours
    )


# ── CUDA helper ──────────────────────────────────────────────────────────────

def cuda_ld_path():
    try:
        import nvidia
        p = os.path.dirname(nvidia.__file__)
        return ":".join(os.path.join(p, d, "lib") for d in os.listdir(p))
    except Exception:
        return ""


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()
    accumulation_time, date_str, hour, delete_forecasts, run_ELR = resolve_args(args)
    year = date_str[:4]

    print(f"[{DATASET_NAME.upper()}] Producing {accumulation_time}h forecast "
          f"initialised {date_str} {hour:02d}00Z.")

    ifs_dir = os.path.join(ROOT, f"{accumulation_time}h_accumulations", "IFS_forecast_data")
    counts_dir = os.path.join(ROOT, "interface", "data", f"counts_{accumulation_time}h")
    valid_hours = VALID_HOURS_6H if accumulation_time == 6 else VALID_HOURS_24H

    # CHIRPS/RFE run forecast_date_MW.py, which does forecast + counts in one pass.
    # IMERG runs forecast_date.py per lead time followed by a separate histogram step.
    uses_combined_forecast_script = DATASET_NAME in ("chirps", "rfe")

    if check_counts_files(counts_dir, date_str, hour, valid_hours) and delete_forecasts:
        print("Histogram counts already exist; nothing to do.")
    else:
        # ── Download IFS data ────────────────────────────────────────────
        download_ifs_data(date_str, hour, accumulation_time, ifs_dir)

        # ── Run forecast ─────────────────────────────────────────────────
        dsr = os.path.join(ROOT, f"{accumulation_time}h_accumulations", "cGAN", "dsrnngan")
        forecast_dir = os.path.join(ROOT, f"{accumulation_time}h_accumulations", "cGAN_forecasts")
        pathlib.Path(forecast_dir).mkdir(exist_ok=True)

        env = os.environ.copy()
        env["CGAN_DATASET"] = DATASET_NAME
        env["CGAN_FIELD_SET"] = _FIELD_SET_ENV.get(DATASET_NAME, "imerg_24h")
        env["PYTHONPATH"] = dsr
        ld = cuda_ld_path()
        if ld:
            env["LD_LIBRARY_PATH"] = ld + ":" + env.get("LD_LIBRARY_PATH", "")

        if uses_combined_forecast_script:
            # forecast_date_MW.py lives alongside forecast_date.py in dsr; its yaml
            # config lives under the dataset's own data_root (datasets/<name>/<accum>h/),
            # not the shared cGAN/ tree, since that only carries IMERG's model assets.
            config = os.path.join(ROOT, DATASET_CFG["data_root"],
                                  f"{accumulation_time}h", "forecast_operational.yaml")
            if not os.path.isfile(config):
                sys.exit(f"ERROR: missing forecast config for {DATASET_NAME}: {config}")
            print(f"Running {DATASET_NAME} 24h forecast + counts for {date_str}")
            r = subprocess.run(
                ["python", "forecast_date_MW.py", config, date_str],
                cwd=dsr, env=env
            )
            if r.returncode != 0:
                sys.exit(f"ERROR: forecast_date_MW.py failed (exit {r.returncode}).")
        else:
            # IMERG: separate forecast per lead time + histogram step
            forecast_ok = True
            if accumulation_time == 6:
                fpath = os.path.join(forecast_dir, f"GAN_{date_str}_{hour:02d}Z.nc")
                if not has_forecast_output(fpath, min_valid_times=len(valid_hours)):
                    if os.path.isfile(fpath):
                        print(f"{fpath} exists but is incomplete/corrupt; re-generating.")
                        os.remove(fpath)
                    print(f"Running 6h cGAN: forecast_date.py {date_str} {hour}")
                    r = subprocess.run(
                        ["python", "forecast_date.py", date_str, str(hour)],
                        cwd=dsr, env=env
                    )
                    forecast_ok = (r.returncode == 0
                                   and has_forecast_output(fpath, min_valid_times=len(valid_hours)))
                    if not forecast_ok:
                        print(f"ERROR: forecast_date.py did not produce a complete "
                              f"forecast (exit {r.returncode}).")
            else:
                for lead_idx in range(7):
                    fpath = os.path.join(forecast_dir, f"GAN_{date_str}_{hour:02d}Z_v{lead_idx}.nc")
                    if not has_forecast_output(fpath):
                        if os.path.isfile(fpath):
                            print(f"{fpath} exists but is incomplete/corrupt; re-generating.")
                            os.remove(fpath)
                        print(f"Running 24h cGAN: forecast_date.py {lead_idx} {date_str}")
                        r = subprocess.run(
                            ["python", "forecast_date.py", str(lead_idx), date_str],
                            cwd=dsr, env=env
                        )
                        if r.returncode != 0 or not has_forecast_output(fpath):
                            print(f"ERROR: forecast_date.py lead {lead_idx} did not "
                                  f"produce a complete forecast (exit {r.returncode}).")
                            forecast_ok = False

            # IMERG histogram computation (separate step). Skipped on a failed/incomplete
            # forecast above -- forecast2histogram*.py assumes every lead file it opens is
            # complete and crashes hard (not a clean error) otherwise.
            if not forecast_ok:
                sys.exit(f"ERROR: {DATASET_NAME} {accumulation_time}h forecast for "
                         f"{date_str} {hour:02d}00Z incomplete; histogram step skipped.")
            if not check_counts_files(counts_dir, date_str, hour, valid_hours):
                pathlib.Path(counts_dir).mkdir(exist_ok=True)
                pathlib.Path(os.path.join(counts_dir, year)).mkdir(exist_ok=True)
                hist_script = ("forecast2histogram_lowRAM.py" if accumulation_time == 6
                               else "forecast2histogram_7d_lowRAM.py")
                run_dir = os.path.join(ROOT, f"{accumulation_time}h_accumulations")
                print(f"Computing {accumulation_time}h histograms for {date_str}.")
                subprocess.run(["python", hist_script, date_str, str(hour)], cwd=run_dir)

    # ── ELR (IMERG 24h only) ─────────────────────────────────────────────
    if run_ELR and hour == 0 and accumulation_time == 24 and DATASET_NAME == "imerg":
        elr_dir = os.path.join(ROOT, "ELR")
        if os.path.isfile(os.path.join(elr_dir, "run_ELR.py")):
            print("Running ELR 24h forecasts.")
            subprocess.run(
                ["python", "run_ELR.py", "--date", date_str, "--model", "GAN",
                 "--accumulation", "24h_accumulations"],
                cwd=elr_dir
            )

    # ── Refresh interface dates ──────────────────────────────────────────
    run_dir = os.path.join(ROOT, f"{accumulation_time}h_accumulations")
    fad = os.path.join(run_dir, "find_available_dates.py")
    if os.path.isfile(fad):
        print(f"Listing {accumulation_time}h counts for the interface.")
        subprocess.run(["python", "find_available_dates.py"], cwd=run_dir)

    if run_ELR and hour == 0 and DATASET_NAME == "imerg":
        elr_dates = os.path.join(ROOT, "ELR", "ELR_available_dates.py")
        if os.path.isfile(elr_dates):
            print("Listing ELR available dates.")
            subprocess.run(["python", "ELR_available_dates.py"], cwd=os.path.join(ROOT, "ELR"))

    # ── Delete raw forecasts if requested ────────────────────────────────
    if delete_forecasts:
        forecast_dir = os.path.join(ROOT, f"{accumulation_time}h_accumulations", "cGAN_forecasts")
        if accumulation_time == 6:
            raw = os.path.join(forecast_dir, f"GAN_{date_str}_{hour:02d}Z.nc")
            if os.path.isfile(raw):
                print(f"Deleting {raw}")
                os.remove(raw)
        else:
            for lead_idx in range(7):
                raw = os.path.join(forecast_dir, f"GAN_{date_str}_{hour:02d}Z_v{lead_idx}.nc")
                if os.path.isfile(raw):
                    print(f"Deleting {raw}")
                    os.remove(raw)

    print("Script run_forecast.py is done!")
