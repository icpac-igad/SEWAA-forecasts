#!/usr/bin/env python
"""Run the operational cGAN-CHIRPS (run07) 24h forecast for one date.

Downloads IFS_<date>_00Z.nc from the Oxford archive, runs forecast_date_MW.py (50-member
ensemble + interface histogram counts in one pass), then refreshes available_dates.json.

    python run_forecast.py                          # yesterday (UTC)
    python run_forecast.py --date 20260604          # a specific date
"""
import argparse
import os
import sys
import subprocess
import pathlib
import platform
import datetime


ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG = "forecast_run07_operational.yaml"
VALID_HOURS_24H = [6, 30, 54, 78, 102, 126, 150]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--accumulation", default="24h",
                   help="Accumulation window. Only 24h is deployed for run07.")
    p.add_argument("--date", default=None, help="Init date YYYYMMDD (default: yesterday UTC)")
    p.add_argument("--time", default="0000", help="Init time HHMM (24h forecasts use 0000)")
    p.add_argument("--delete_forecasts", default=None,
                   help="Delete the raw ensemble once counts are computed (Y/N)")
    p.add_argument("--disable_ELR", nargs="*", default=None,
                   help="(kept for CLI compatibility; ELR is not run for run13)")
    a = p.parse_args()

    if a.accumulation not in ("24h", "24"):
        sys.exit("ERROR: this deployment runs 24h accumulations only (CHIRPS run07 is a 24h model).")

    if a.date is not None:
        if len(a.date) != 8:
            sys.exit("ERROR: --date must be YYYYMMDD.")
        date_str = a.date
    else:
        date_str = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime("%Y%m%d")

    if a.time != "0000":
        sys.exit("ERROR: 24h forecasts initialise at 0000 only.")

    delete_forecasts = str(a.delete_forecasts).lower() in ("t", "y") if a.delete_forecasts else False
    return date_str, delete_forecasts


def counts_present(date_str):
    year = date_str[:4]
    cdir = os.path.join(ROOT, "interface", "data", "counts_24h", year)
    return all(os.path.isfile(os.path.join(cdir, f"counts_{date_str}_00_{h}h.nc"))
               for h in VALID_HOURS_24H)


def download_ifs(date_str):
    year = date_str[:4]
    ifs_dir = os.path.join(ROOT, "24h_accumulations", "IFS_forecast_data")
    pathlib.Path(ifs_dir).mkdir(parents=True, exist_ok=True)
    fname = f"IFS_{date_str}_00Z.nc"
    dst = os.path.join(ifs_dir, fname)
    if os.path.isfile(dst):
        # a partial/interrupted download leaves a corrupt file; validate it opens
        try:
            import xarray as xr
            xr.open_dataset(dst).close()
            print(f"{dst} already exists and is valid.")
            return dst
        except Exception:
            print(f"{dst} exists but is corrupt/incomplete; re-downloading.")
            os.remove(dst)

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
        sys.exit(f"Unable to fetch {fname} from Oxford (HTTP {r.stdout.strip()}). "
                 f"The IFS file may not be published yet.")
    return dst


def cuda_ld_path():
    """Point LD_LIBRARY_PATH at the venv's bundled nvidia CUDA libs (GPU). No-op on CPU."""
    try:
        import nvidia
        p = os.path.dirname(nvidia.__file__)
        return ":".join(os.path.join(p, d, "lib") for d in os.listdir(p))
    except Exception:
        return ""


def run_forecast(date_str):
    dsr = os.path.join(ROOT, "24h_accumulations", "cGAN", "dsrnngan")
    env = os.environ.copy()
    env["CGAN_FIELD_SET"] = "run07"      # run07 uses 14 fields (climatology + 13 IFS) = 28ch
    env["PYTHONPATH"] = dsr
    ld = cuda_ld_path()
    if ld:
        env["LD_LIBRARY_PATH"] = ld + ":" + env.get("LD_LIBRARY_PATH", "")
    print(f"Running run07 24h forecast + counts for {date_str}")
    r = subprocess.run(["python", "../../forecast_date_MW.py", CONFIG, date_str],
                       cwd=dsr, env=env)
    if r.returncode != 0:
        sys.exit(f"ERROR: forecast_date_MW.py failed for {date_str} (exit {r.returncode}).")


def refresh_interface():
    run_dir = os.path.join(ROOT, "24h_accumulations")
    fad = os.path.join(run_dir, "find_available_dates.py")
    if os.path.isfile(fad):
        print("Listing 24h counts for the interface.")
        subprocess.run(["python", "find_available_dates.py"], cwd=run_dir)


def main():
    date_str, delete_forecasts = parse_args()
    print(f"Producing 24h cGAN-CHIRPS (run07) forecast initialised {date_str} 0000Z.")

    if counts_present(date_str):
        print("Histogram counts already exist for this date; nothing to do.")
    else:
        download_ifs(date_str)
        run_forecast(date_str)

    refresh_interface()

    if delete_forecasts:
        year = date_str[:4]
        raw = os.path.join(ROOT, "24h_accumulations", "cGAN",
                           "fcst_run07_operational", f"GAN_fcst_crps_{date_str}_00Z.nc")
        if os.path.isfile(raw):
            print(f"Deleting raw ensemble {raw}")
            os.remove(raw)

    print("Script run_forecast.py is done!")


if __name__ == "__main__":
    main()
