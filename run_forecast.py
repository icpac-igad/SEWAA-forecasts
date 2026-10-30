#!/usr/bin/env python
"""Unified operational forecast runner for all datasets.

Dataset selection via CGAN_DATASET environment variable (default: imerg).
Supports IMERG (6h + 24h), CHIRPS (24h), RFE (24h). IFS input data is fetched
over HTTP from the Oxford archive, falling back to megacorr.dynu.net and then the
ICPAC data portal (see IFS_SOURCES).

    CGAN_DATASET=imerg python run_forecast.py --accumulation 24h --date 20260920
    CGAN_DATASET=chirps python run_forecast.py --date 20260920
    CGAN_DATASET=rfe python run_forecast.py --date 20260920
"""
import argparse
import glob
import os
import sys
import time
import subprocess
import pathlib
import platform
import socket
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dataset_config import get_active_dataset, get_active_dataset_name  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
DATASET_NAME = get_active_dataset_name()
DATASET_CFG = get_active_dataset()
# Prefix for every log line, so output from the imerg/rfe/chirps jobs (which share the IFS
# folder and often run side by side) can be told apart.
TAG = f"[{DATASET_NAME.upper()}]"

# Where forecast data lives. Under docker-compose / Cloud Run the store's folders are mounted
# over the in-repo paths (docker-compose.yml, cloudbuild.yaml) and the image sets
# CGAN_DATA_MOUNTED=1, so those paths are used as-is. Run anywhere else (e.g. from a local
# .venv) everything goes under one store root instead, ${STORE:-./store}, with the same
# layout docker-compose uses. A relative STORE is resolved against the repo root.
DATA_MOUNTED = os.environ.get("CGAN_DATA_MOUNTED", "").lower() in ("1", "true", "yes")
STORE = os.path.join(ROOT, os.path.expanduser(os.path.expandvars(os.environ.get("STORE", "store"))))


def data_dirs(accumulation_time):
    """Return (ifs_dir, forecast_dir, interface_dir) for the active dataset."""
    if DATA_MOUNTED:
        accum_root = os.path.join(ROOT, f"{accumulation_time}h_accumulations")
        return (os.path.join(accum_root, "IFS_forecast_data"),
                os.path.join(accum_root, "cGAN_forecasts"),
                os.path.join(ROOT, "interface", "data"))
    return (os.path.join(STORE, "forecasts", f"IFS_{accumulation_time}h_forecast_data"),
            os.path.join(STORE, "forecasts", DATASET_NAME, f"{accumulation_time}h", "cGAN_forecasts"),
            os.path.join(STORE, "interface", DATASET_NAME))


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
            sys.exit(f"{TAG} ERROR: unknown accumulation '{args.accumulation}'. Use 6h or 24h.")
        if f"{accumulation_time}h" not in supported:
            sys.exit(f"{TAG} ERROR: {DATASET_NAME} only supports {supported} accumulations.")
    else:
        accumulation_time = int(default_accum.replace("h", ""))

    if args.date is not None:
        if len(args.date) != 8:
            sys.exit(f"{TAG} ERROR: --date must be YYYYMMDD.")
        date_str = args.date
    else:
        date_str = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime("%Y%m%d")

    hour = int(args.time[:2]) if args.time else 0

    if accumulation_time == 6 and hour not in (0, 6, 12, 18):
        sys.exit(f"{TAG} ERROR: 6h forecasts use times 0000, 0600, 1200, 1800.")
    if accumulation_time == 24 and hour != 0:
        sys.exit(f"{TAG} ERROR: 24h forecasts initialise at 0000 only.")

    delete = str(args.delete_forecasts).lower() in ("t", "y") if args.delete_forecasts else False
    run_elr = args.disable_ELR is None

    return accumulation_time, date_str, hour, delete, run_elr


# ── IFS download ──────────────────────────────────────────────────────────────
# A *.part file untouched for this long belongs to a download that was killed (curl writes
# continuously, so a live download keeps refreshing its mtime).
STALE_PART_SECONDS = 3600
# curl has no overall timeout by default, so a connection that stays open but stops sending
# data would hang the run indefinitely -- and with it every other init time queued behind
# it in the same job. Abort a transfer slower than CURL_SPEED_LIMIT bytes/s for
# CURL_SPEED_TIME seconds; --retry then resumes it (-C -) on a fresh connection.
CURL_TIMEOUT_ARGS = ["--connect-timeout", "30", "--speed-limit", "1024", "--speed-time", "300"]
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
     "{accum}h_accumulations/{year}/{fname}"),
]


# The lock only avoids duplicate downloads: the temp-file + rename below
# already keeps a reader from ever seeing a partial file, so on timeout we download anyway.
IFS_LOCK_WAIT_SECONDS = 1800
IFS_LOCK_POLL_SECONDS = 15
# The holder heartbeats every 60s (job_lock.HEARTBEAT_SECONDS); a download killed mid-way
# frees its lock after this long instead of job_lock's default 10 minutes.
IFS_LOCK_STALE_SECONDS = 180


def download_ifs_data(date_str, hour, accumulation_time, ifs_dir):
    """Fetch IFS forecast data into the shared ifs_dir, once across all jobs.

    Exits the program if the file is unavailable from every known source.
    """
    pathlib.Path(ifs_dir).mkdir(exist_ok=True, parents=True)
    fname = f"IFS_{date_str}_{hour:02d}Z.nc"
    dst = os.path.join(ifs_dir, fname)

    if os.path.isfile(dst) and is_valid_netcdf(dst):
        print(f"{TAG} {dst} already exists and is valid.")
        return dst

    try:
        from job_lock import wait_for_lock
    except ImportError:  # fcntl is POSIX-only; download unlocked elsewhere
        return _fetch_ifs_data(date_str, accumulation_time, ifs_dir, fname, dst)

    with wait_for_lock(f"ifs-{accumulation_time}h-{date_str}-{hour:02d}z",
                       timeout=IFS_LOCK_WAIT_SECONDS, poll_seconds=IFS_LOCK_POLL_SECONDS,
                       stale_seconds=IFS_LOCK_STALE_SECONDS,
                       local_dir=os.path.join(ifs_dir, ".locks"),
                       until=lambda: os.path.isfile(dst) and is_valid_netcdf(dst)):
        # Another job may have finished the download while this one waited for the lock.
        if os.path.isfile(dst) and is_valid_netcdf(dst):
            print(f"{TAG} {dst} downloaded by another job; using it.")
            return dst
        return _fetch_ifs_data(date_str, accumulation_time, ifs_dir, fname, dst)


def _fetch_ifs_data(date_str, accumulation_time, ifs_dir, fname, dst):
    """Download fname into dst, trying each mirror in IFS_SOURCES in turn."""
    if os.path.isfile(dst):
        print(f"{TAG} {dst} exists but is corrupt/incomplete; re-downloading.")
        os.remove(dst)

    # Temp files are named per-PID, so a killed process's partial download is never
    # resumed by a later run -- remove stale ones instead of letting them pile up.
    for part in glob.glob(f"{glob.escape(dst)}.*.part"):
        try:
            if time.time() - os.path.getmtime(part) > STALE_PART_SECONDS:
                print(f"{TAG} Removing stale partial download {part}")
                os.remove(part)
        except OSError:
            pass

    year = date_str[:4]
    oblivion = "nul" if platform.system() == "Windows" else "/dev/null"

    for name, url_template in IFS_SOURCES:
        url = url_template.format(accum=accumulation_time, year=year, fname=fname)
        print(f"{TAG} Checking {name} for {fname}")
        r = subprocess.run(["curl", "-Isw", "%{http_code}", "--connect-timeout", "30", "--max-time", "60",
                            url, "-o", oblivion],
                           capture_output=True, text=True)
        if r.stdout.strip().endswith("200"):
            print(f"{TAG} Downloading {fname} from {name} -> {ifs_dir}/")
            # Download to a per-process temp file and only move it into place once it
            # opens as valid netCDF. curl's exit code alone isn't enough (a dropped
            # connection mid-transfer leaves a truncated file), and writing straight to
            # dst lets the forecast step -- or another job sharing this folder -- read a
            # half-written file ("NetCDF: HDF error").
            # Host + PID: jobs in different containers share this folder and can share a PID.
            tmp = f"{dst}.{socket.gethostname()}-{os.getpid()}.part"
            for attempt in range(1, 4):
                c = subprocess.run(["curl", "-fL", "--retry", "20", "--retry-delay", "5",
                                    "--retry-all-errors", *CURL_TIMEOUT_ARGS, "-C", "-", url, "-o", tmp])
                if c.returncode == 0 and is_valid_netcdf(tmp):
                    os.replace(tmp, dst)
                    return dst
                print(f"{TAG} Download of {fname} from {name} failed or is incomplete "
                      f"(curl exit {c.returncode}, attempt {attempt}/3).")
                # A clean curl exit with an unreadable file can't be fixed by resuming.
                if c.returncode == 0 and os.path.isfile(tmp):
                    os.remove(tmp)
            if os.path.isfile(tmp):
                os.remove(tmp)
            continue
        print(f"{TAG} {fname} not available from {name} (HTTP {r.stdout.strip()}).")

    sources = ", ".join(name for name, _ in IFS_SOURCES)
    sys.exit(f"{TAG} ERROR: {fname} is not available from any known source ({sources}).")


# ── Counts checking ──────────────────────────────────────────────────────────

def check_counts_files(counts_path, date_str, hour, valid_hours):
    year = date_str[:4]
    return all(
        os.path.isfile(os.path.join(counts_path, year, f"counts_{date_str}_{hour:02d}_{h}h.nc"))
        for h in valid_hours
    )


# ── ELR checking ─────────────────────────────────────────────────────────────

# ELR reads only the lead-1 raw ensemble (run_ELR.py: day = np.arange(1, 2)).
ELR_LEAD_IDX = 1
# Region level per country that ELR_available_dates.py publishes to the interface.
ELR_COUNTRY_REGIONTYPE = {"Kenya": "subcounty", "Ethiopia": "subcounty", "Rwanda": "county"}


def check_elr_files(interface_dir, date_str):
    elr_dir = os.path.join(interface_dir, "ELR_predictions", "24h_accumulations")
    return all(
        os.path.isfile(os.path.join(elr_dir, country, regiontype,
                                    f"GAN_{date_str}_ELR_v{ELR_LEAD_IDX}.nc"))
        for country, regiontype in ELR_COUNTRY_REGIONTYPE.items()
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

    print(f"{TAG} Producing {accumulation_time}h forecast "
          f"initialised {date_str} {hour:02d}00Z.")

    ifs_dir, forecast_dir, interface_dir = data_dirs(accumulation_time)
    counts_dir = os.path.join(interface_dir, f"counts_{accumulation_time}h")
    print(f"{TAG} Data folders: IFS {ifs_dir}, forecasts {forecast_dir}, interface {interface_dir}")

    # Every child script reads/writes these folders from env, falling back to its in-repo
    # relative defaults when run on its own.
    data_env = os.environ.copy()
    data_env.update(CGAN_IFS_DIR=ifs_dir, CGAN_FORECASTS_DIR=forecast_dir,
                    CGAN_INTERFACE_DATA_DIR=interface_dir)
    valid_hours = VALID_HOURS_6H if accumulation_time == 6 else VALID_HOURS_24H

    # CHIRPS/RFE run forecast_date_MW.py, which writes a lead's forecast + counts in one pass.
    # IMERG runs forecast_date.py per lead time followed by a separate histogram step.
    # Both run one process per lead, so gen.predict()'s memory growth is freed between leads.
    uses_combined_forecast_script = DATASET_NAME in ("chirps", "rfe")

    # ELR runs for every 24h dataset, on the lead-1 raw ensemble (GAN_<date>_00Z_v1.nc).
    elr_needed = run_ELR and hour == 0 and accumulation_time == 24
    counts_done = check_counts_files(counts_dir, date_str, hour, valid_hours)
    elr_done = check_elr_files(interface_dir, date_str) if elr_needed else True

    if counts_done and delete_forecasts and elr_done:
        print(f"{TAG} Histogram counts" + (" and ELR outputs" if elr_needed else "")
              + " already exist; nothing to do.")
    else:
        if counts_done and not elr_done:
            # Counts survived but ELR didn't (e.g. ELR crashed, or the raw ensemble was
            # deleted before ELR ran). Regenerate just the lead ELR needs; the histogram
            # step below is skipped because the counts are already there.
            print(f"{TAG} Histogram counts exist but ELR outputs for {date_str} are missing; "
                  f"rerunning ELR (regenerating the lead {ELR_LEAD_IDX} raw forecast if needed).")
        # ── Download IFS data ────────────────────────────────────────────
        download_ifs_data(date_str, hour, accumulation_time, ifs_dir)

        # ── Run forecast ─────────────────────────────────────────────────
        dsr = os.path.join(ROOT, f"{accumulation_time}h_accumulations", "cGAN", "dsrnngan")
        pathlib.Path(forecast_dir).mkdir(exist_ok=True, parents=True)

        env = data_env.copy()
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
                sys.exit(f"{TAG} ERROR: missing forecast config for {DATASET_NAME}: {config}")
            # A lead runs if its counts are missing, or if it's the lead ELR still needs and
            # its raw ensemble is gone. Leads already done are skipped, so a run killed at
            # the task timeout resumes where it stopped.
            forecast_ok = True
            for lead_idx in range(7):
                fpath = os.path.join(forecast_dir, f"GAN_{date_str}_{hour:02d}Z_v{lead_idx}.nc")
                cpath = os.path.join(counts_dir, year,
                                     f"counts_{date_str}_{hour:02d}_{valid_hours[lead_idx]}h.nc")
                need_counts = not os.path.isfile(cpath)
                need_raw = (lead_idx == ELR_LEAD_IDX and not elr_done
                            and not has_forecast_output(fpath))
                if not (need_counts or need_raw):
                    continue
                if os.path.isfile(fpath):
                    os.remove(fpath)   # partial file from a killed run
                print(f"{TAG} Running {DATASET_NAME} 24h forecast + counts for {date_str} lead {lead_idx}")
                r = subprocess.run(
                    ["python", "forecast_date_MW.py", config, date_str, "--lead", str(lead_idx)],
                    cwd=dsr, env=env
                )
                if r.returncode != 0 or not has_forecast_output(fpath) or not os.path.isfile(cpath):
                    print(f"{TAG} ERROR: forecast_date_MW.py lead {lead_idx} did not produce a "
                          f"complete forecast + counts (exit {r.returncode}).")
                    forecast_ok = False
            if not forecast_ok:
                sys.exit(f"{TAG} ERROR: {DATASET_NAME} 24h forecast for {date_str} incomplete.")
        else:
            # IMERG: separate forecast per lead time + histogram step
            forecast_ok = True
            if accumulation_time == 6:
                fpath = os.path.join(forecast_dir, f"GAN_{date_str}_{hour:02d}Z.nc")
                if not has_forecast_output(fpath, min_valid_times=len(valid_hours)):
                    if os.path.isfile(fpath):
                        print(f"{TAG} {fpath} exists but is incomplete/corrupt; re-generating.")
                        os.remove(fpath)
                    print(f"{TAG} Running 6h cGAN: forecast_date.py {date_str} {hour}")
                    r = subprocess.run(
                        ["python", "forecast_date.py", date_str, str(hour)],
                        cwd=dsr, env=env
                    )
                    forecast_ok = (r.returncode == 0
                                   and has_forecast_output(fpath, min_valid_times=len(valid_hours)))
                    if not forecast_ok:
                        print(f"{TAG} ERROR: forecast_date.py did not produce a complete "
                              f"forecast (exit {r.returncode}).")
            else:
                lead_idxs = [ELR_LEAD_IDX] if counts_done else range(7)
                for lead_idx in lead_idxs:
                    fpath = os.path.join(forecast_dir, f"GAN_{date_str}_{hour:02d}Z_v{lead_idx}.nc")
                    if not has_forecast_output(fpath):
                        if os.path.isfile(fpath):
                            print(f"{TAG} {fpath} exists but is incomplete/corrupt; re-generating.")
                            os.remove(fpath)
                        print(f"{TAG} Running 24h cGAN: forecast_date.py {lead_idx} {date_str}")
                        r = subprocess.run(
                            ["python", "forecast_date.py", str(lead_idx), date_str],
                            cwd=dsr, env=env
                        )
                        if r.returncode != 0 or not has_forecast_output(fpath):
                            print(f"{TAG} ERROR: forecast_date.py lead {lead_idx} did not "
                                  f"produce a complete forecast (exit {r.returncode}).")
                            forecast_ok = False

            # IMERG histogram computation (separate step). Skipped on a failed/incomplete
            # forecast above -- forecast2histogram*.py assumes every lead file it opens is
            # complete and crashes hard (not a clean error) otherwise.
            if not forecast_ok:
                sys.exit(f"{TAG} ERROR: {DATASET_NAME} {accumulation_time}h forecast for "
                         f"{date_str} {hour:02d}00Z incomplete; histogram step skipped.")
            if not check_counts_files(counts_dir, date_str, hour, valid_hours):
                pathlib.Path(os.path.join(counts_dir, year)).mkdir(exist_ok=True, parents=True)
                hist_script = ("forecast2histogram_lowRAM.py" if accumulation_time == 6
                               else "forecast2histogram_7d_lowRAM.py")
                run_dir = os.path.join(ROOT, f"{accumulation_time}h_accumulations")
                print(f"{TAG} Computing {accumulation_time}h histograms for {date_str}.")
                subprocess.run(["python", hist_script, date_str, str(hour)], cwd=run_dir, env=data_env)

    # ── ELR (24h, all datasets) ──────────────────────────────────────────
    if elr_needed and not elr_done:
        elr_dir = os.path.join(ROOT, "ELR")
        elr_input = os.path.join(forecast_dir, f"GAN_{date_str}_00Z_v{ELR_LEAD_IDX}.nc")
        if not os.path.isfile(elr_input):
            # The forecast step above should have (re)generated it; don't let run_ELR.py
            # crash with FileNotFoundError if it somehow didn't.
            print(f"{TAG} ERROR: skipping ELR, raw forecast {elr_input} not present.")
        elif os.path.isfile(os.path.join(elr_dir, "run_ELR.py")):
            print(f"{TAG} Running ELR 24h forecasts.")
            r = subprocess.run(
                ["python", "run_ELR.py", "--date", date_str, "--model", "GAN",
                 "--accumulation", "24h_accumulations"],
                cwd=elr_dir, env=data_env
            )
            elr_done = check_elr_files(interface_dir, date_str)
            if not elr_done:
                print(f"{TAG} ERROR: run_ELR.py did not produce all ELR outputs for {date_str} "
                      f"(exit {r.returncode}).")

    # ── Refresh interface dates ──────────────────────────────────────────
    run_dir = os.path.join(ROOT, f"{accumulation_time}h_accumulations")
    fad = os.path.join(run_dir, "find_available_dates.py")
    if os.path.isfile(fad):
        print(f"{TAG} Listing {accumulation_time}h counts for the interface.")
        subprocess.run(["python", "find_available_dates.py"], cwd=run_dir, env=data_env)

    if elr_needed:
        elr_dates = os.path.join(ROOT, "ELR", "ELR_available_dates.py")
        if os.path.isfile(elr_dates):
            print(f"{TAG} Listing ELR available dates.")
            subprocess.run(["python", "ELR_available_dates.py"], cwd=os.path.join(ROOT, "ELR"),
                           env=data_env)

    # ── Delete raw forecasts if requested ────────────────────────────────
    # Raw ensembles are kept until ELR has consumed them, so a failed ELR run can be
    # retried without regenerating the forecast.
    if delete_forecasts and not elr_done:
        print(f"{TAG} Keeping raw forecasts for {date_str}: ELR outputs are incomplete.")
    elif delete_forecasts:
        if accumulation_time == 6:
            raw = os.path.join(forecast_dir, f"GAN_{date_str}_{hour:02d}Z.nc")
            if os.path.isfile(raw):
                print(f"{TAG} Deleting {raw}")
                os.remove(raw)
        else:
            for lead_idx in range(7):
                raw = os.path.join(forecast_dir, f"GAN_{date_str}_{hour:02d}Z_v{lead_idx}.nc")
                if os.path.isfile(raw):
                    print(f"{TAG} Deleting {raw}")
                    os.remove(raw)

    print(f"{TAG} Script run_forecast.py is done!")
