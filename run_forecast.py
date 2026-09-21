#!/usr/bin/env python
"""Unified operational forecast runner for all datasets.

Dataset selection via CGAN_DATASET environment variable (default: imerg).
Supports IMERG (6h + 24h, SCP from ECMWF), CHIRPS (24h, Oxford), RFE (24h, Oxford).

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

# Dataset-specific forecast config names
_FORECAST_CONFIGS = {
    "imerg": "forecast.yaml",
    "chirps": "forecast_run07_operational.yaml",
    "rfe": "forecast_run13_operational.yaml",
}

# Dataset-specific field set env var values
_FIELD_SET_ENV = {
    "imerg": "imerg_24h",
    "chirps": "run07",
    "rfe": "run11",
}


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


# ── IFS download methods ─────────────────────────────────────────────────────

def download_ifs_ecmwf(date_str, hour, ifs_dir, operational_subdir="Operational"):
    """Download IFS data via SCP from ECMWF (IMERG)."""
    pathlib.Path(ifs_dir).mkdir(exist_ok=True, parents=True)
    fname = f"IFS_{date_str}_{hour:02d}Z.nc"
    dst = os.path.join(ifs_dir, fname)

    if os.path.isfile(dst):
        print(f"{dst} already exists.")
        return dst

    print(f"Copying {fname} from gbmc to {ifs_dir}/.")
    cp = subprocess.run(
        ["scp", f"gbmc@136.156.130.165:/data/{operational_subdir}/{fname}", ifs_dir]
    )
    if cp.returncode != 0:
        print(f"Unable to copy {fname} from gbmc. Trying with host key verification disabled!")
        cp = subprocess.run(
            ["scp", "-o StrictHostKeyChecking=no",
             f"gbmc@136.156.130.165:/data/{operational_subdir}/{fname}", ifs_dir]
        )
        if cp.returncode != 0:
            print(f"unresolvable failure to copy {fname} from gbmc")
            return None
    return dst


def download_ifs_oxford(date_str, ifs_dir):
    """Download IFS data via curl from Oxford archive (CHIRPS/RFE)."""
    pathlib.Path(ifs_dir).mkdir(exist_ok=True, parents=True)
    fname = f"IFS_{date_str}_00Z.nc"
    dst = os.path.join(ifs_dir, fname)

    if os.path.isfile(dst):
        try:
            import xarray as xr
            xr.open_dataset(dst).close()
            print(f"{dst} already exists and is valid.")
            return dst
        except Exception:
            print(f"{dst} exists but is corrupt; re-downloading.")
            os.remove(dst)

    year = date_str[:4]
    oblivion = "nul" if platform.system() == "Windows" else "/dev/null"
    url = (f"https://rain.physics.ox.ac.uk/ICPAC/operational/24h_accumulations/"
           f"IFS_forecast_data/{year}/{fname}")
    print(f"Checking University of Oxford for {fname}")
    r = subprocess.run(["curl", "-Isw", "%{http_code}", url, "-o", oblivion],
                       capture_output=True, text=True)
    if r.stdout.strip().endswith("200"):
        print(f"Downloading {fname} from University of Oxford -> {ifs_dir}/")
        subprocess.run(["curl", "-fL", "--retry", "20", "--retry-delay", "5",
                        "-C", "-", url, "-o", dst])
    else:
        sys.exit(f"Unable to fetch {fname} from Oxford (HTTP {r.stdout.strip()}).")
    return dst


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

    download_source = DATASET_CFG["download_source"]
    ifs_dir = os.path.join(ROOT, f"{accumulation_time}h_accumulations", "IFS_forecast_data")
    counts_dir = os.path.join(ROOT, "interface", "data", f"counts_{accumulation_time}h")

    # ── Download IFS data ────────────────────────────────────────────────
    if download_source == "ecmwf":
        subdir = "Operational" if accumulation_time == 6 else "Operational_7d"
        ifs_file = download_ifs_ecmwf(date_str, hour, ifs_dir, subdir)
        if ifs_file is None:
            sys.exit(1)
    elif download_source == "oxford":
        ifs_file = download_ifs_oxford(date_str, ifs_dir)

    # ── Check if counts already exist ────────────────────────────────────
    valid_hours = VALID_HOURS_6H if accumulation_time == 6 else VALID_HOURS_24H
    if check_counts_files(counts_dir, date_str, hour, valid_hours) and delete_forecasts:
        print("Histogram counts already exist; nothing to do.")
    else:
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

        if download_source == "oxford":
            # CHIRPS/RFE: forecast_date_MW.py does forecast + counts in one pass
            config = _FORECAST_CONFIGS.get(DATASET_NAME, "forecast.yaml")
            print(f"Running {DATASET_NAME} 24h forecast + counts for {date_str}")
            r = subprocess.run(
                ["python", "../../forecast_date_MW.py", config, date_str],
                cwd=dsr, env=env
            )
            if r.returncode != 0:
                sys.exit(f"ERROR: forecast_date_MW.py failed (exit {r.returncode}).")
        else:
            # IMERG: separate forecast per lead time + histogram step
            if accumulation_time == 6:
                fname = f"GAN_{date_str}_{hour:02d}Z.nc"
                if not os.path.isfile(os.path.join(forecast_dir, fname)):
                    print(f"Running 6h cGAN: forecast_date.py {date_str} {hour}")
                    subprocess.run(
                        ["python", "forecast_date.py", date_str, str(hour)],
                        cwd=dsr, env=env
                    )
            else:
                for lead_idx in range(7):
                    fname = f"GAN_{date_str}_{hour:02d}Z_v{lead_idx}.nc"
                    if not os.path.isfile(os.path.join(forecast_dir, fname)):
                        print(f"Running 24h cGAN: forecast_date.py {lead_idx} {date_str}")
                        subprocess.run(
                            ["python", "forecast_date.py", str(lead_idx), date_str],
                            cwd=dsr, env=env
                        )

            # IMERG histogram computation (separate step)
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
