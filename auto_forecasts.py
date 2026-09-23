#!/usr/bin/env python
"""Batch forecast generator: the Cloud Run Jobs entrypoint.

Backfills run_forecast.py over a date range for ONE dataset+accumulation "channel"
(imerg-6h, imerg-24h, chirps-24h, rfe-24h), then exits. It does not loop or sleep
itself -- Cloud Scheduler re-triggers each channel's job on a cron (see
deploy/setup-cloud-scheduler.sh), one Cloud Run Job per channel, so a slow CHIRPS
run never queues behind IMERG the way start_forecasting.py's single-process,
sequential polling loop would.

For a docker-compose / always-on deployment, use start_forecasting.py instead --
it polls continuously inside one long-running container per dataset.

    python auto_forecasts.py --dataset imerg --accumulation 6h
    python auto_forecasts.py --dataset chirps --accumulation 24h --days_to_check 2
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime, timedelta

from pandas import date_range

from dataset_config import DATASETS, get_active_dataset_name

# Valid initialisation times per accumulation window (mirrors run_forecast.py's
# resolve_args validation).
VALID_TIMES = {
    "6h": ["0000", "0600", "1200", "1800"],
    "24h": ["0000"],
}


def gen_forecast_request(
    dataset: str,
    forecast_date: str,
    accumulation: str,
    time: str,
    delete_forecasts: str = "Y",
) -> bool:
    """Run one run_forecast.py invocation for a single date+time. Returns success."""
    env = os.environ.copy()
    env["CGAN_DATASET"] = dataset
    params = [
        "python",
        "run_forecast.py",
        "--delete_forecasts",
        delete_forecasts,
        "--date",
        forecast_date,
        "--accumulation",
        accumulation,
        "--time",
        time,
    ]
    print(f"[{dataset}] running: {' '.join(params)}")
    result = subprocess.run(params, env=env)
    ok = result.returncode == 0
    status = "done" if ok else f"FAILED (exit {result.returncode})"
    print(f"[{dataset}] {forecast_date} {accumulation} {time}: {status}")
    return ok


def forecast_dates_generator(
    start_date: str | None = None,
    final_date: str | None = None,
    days_to_check: int | None = 2,
) -> list[str]:
    days_to_check = days_to_check if isinstance(days_to_check, int) else 2
    if start_date is None:
        start_dt = datetime.now() - timedelta(days=days_to_check)
    else:
        try:
            start_dt = datetime.strptime(start_date, "%Y%m%d")
        except Exception as err:
            print(
                f"failed to parse start_date {start_date} to a valid date object with error {err}"
            )
            start_dt = datetime.now() - timedelta(days=days_to_check)
            print(f"start date defaulting to {days_to_check} days since today -> {start_dt}")

    if final_date is None:
        final_dt = datetime.now()
    else:
        try:
            final_dt = datetime.strptime(final_date, "%Y%m%d")
        except Exception as err:
            print(
                f"failed to parse final_date {final_date} to a valid date object with error {err}"
            )
            final_dt = datetime.now()
            print(f"final date defaulting to today -> {final_dt}")
    return list(
        sorted(
            [
                dt.strftime("%Y%m%d")
                for dt in date_range(
                    start=start_dt, end=final_dt + timedelta(days=1), freq="D"
                )
            ],
            reverse=True,
        )
    )


def auto_gen_forecasts(
    dataset: str,
    start_date: str | None = None,
    final_date: str | None = None,
    accumulation: str | None = None,
    time: str | None = None,
    days_to_check: int | None = 2,
    delete_forecasts: str | None = "Y",
) -> bool:
    """Backfill every (date, time) combination for one dataset+accumulation channel.

    accumulation defaults to the dataset's own default accumulation (dataset_config.py).
    time defaults to EVERY init time the accumulation supports (e.g. all four
    0000/0600/1200/1800 slots for 6h), not just one -- matching start_forecasting.py's
    per-slot catch-up behaviour -- unless a specific --time is passed.

    Returns True iff every (date, time) run succeeded; the caller should exit
    non-zero on False so Cloud Run Jobs' retry/alerting sees the failure.
    """
    if dataset not in DATASETS:
        sys.exit(f"ERROR: unknown dataset {dataset!r}; pick one of {sorted(DATASETS)}")
    cfg = DATASETS[dataset]

    accumulation = accumulation or cfg["default_accumulation"]
    if accumulation not in cfg["accumulations"]:
        sys.exit(f"ERROR: {dataset} does not support {accumulation!r} accumulations "
                  f"(supports {cfg['accumulations']})")

    times = [time] if time else VALID_TIMES[accumulation]
    delete_forecasts = delete_forecasts or "Y"

    print(
        f"[{dataset}] received request to autogenerate {accumulation} forecasts from "
        f"{start_date} to {final_date} at times {times}"
    )
    forecast_dates = forecast_dates_generator(
        start_date=start_date, final_date=final_date, days_to_check=days_to_check
    )
    print(f"[{dataset}] starting forecasts generation for {' => '.join(forecast_dates)}")

    all_ok = True
    for forecast_date in forecast_dates:
        for t in times:
            ok = gen_forecast_request(
                dataset=dataset,
                forecast_date=forecast_date,
                accumulation=accumulation,
                time=t,
                delete_forecasts=delete_forecasts,
            )
            all_ok = all_ok and ok
    return all_ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""
        Function: Autogenerate cGAN forecasts for one dataset+accumulation channel,
        from a specified start date to a final date, then exit. All parameters are
        optional and can be omitted.

        Arguments:
            --dataset        - which forecast product to generate: imerg, chirps, or rfe.
                                Defaults to $CGAN_DATASET, else imerg.
            --start_date     - generate forecasts starting from this date. By default, the program uses days_to_check days from the date today.
            --final_date     - generate forecasts from start_date to this date. By default, the program uses the date today.
            --days_to_check  - number of forecasts days to be checked since today. Can be used to dynamically generate start_date and final_date.
            --accumulation   - forecast accumulation period. Must be one the chosen dataset supports. Defaults to that dataset's default accumulation.
            --time           - forecast initialization time (0000, 0600, 1200 or 1800). Defaults to every time the chosen accumulation supports.

        Returns:
            Exit code 0 if every forecast in the range succeeded, 1 otherwise.
        """,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        help="Forecast product/channel to generate: imerg, chirps, or rfe",
        choices=sorted(DATASETS),
        default=get_active_dataset_name(),
    )
    parser.add_argument(
        "--start_date",
        help="Forecasts generation start date in format (YYYYMMDD)",
        default=None,
        type=str,
    )
    parser.add_argument(
        "--final_date",
        help="Forecasts generation start date in format (YYYYMMDD)",
        default=None,
        type=str,
    )
    parser.add_argument(
        "--days_to_check",
        help="Forecast days to be checked",
        default=2,
        type=int,
    )
    parser.add_argument(
        "--accumulation",
        help="How long rainfall is accumulated for. Must be supported by --dataset. "
             "Defaults to that dataset's default accumulation.",
        default=None,
        type=str,
    )
    parser.add_argument(
        "--time",
        help="Forecast initialisation time (HHMM). Defaults to every time the "
             "chosen accumulation supports.",
        default=None,
        type=str,
    )
    parser.add_argument(
        "--delete_forecasts",
        help="Should forecasts be deleted or not (Y/N)",
        default="Y",
        type=str,
    )
    args = parser.parse_args()
    succeeded = auto_gen_forecasts(
        dataset=args.dataset,
        start_date=args.start_date,
        final_date=args.final_date,
        time=args.time,
        accumulation=args.accumulation,
        days_to_check=args.days_to_check,
        delete_forecasts=args.delete_forecasts,
    )
    sys.exit(0 if succeeded else 1)
