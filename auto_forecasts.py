from typing import Literal
from pandas import date_range
import argparse
import subprocess
from datetime import datetime, timedelta


def gen_forecast_request(
    forecast_date: str,
    accumulation: Literal["6h", "24h"] | None = "6h",
    time: Literal["0000", "0600", "1200", "1800"] | None = "0000",
    delete_forecasts: Literal["Y", "N"] | None = "Y",
) -> None:
    accumulation = accumulation if accumulation is not None else "6h"
    time = time if time is not None else "0000"
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
    subprocess.run(params)
    print(f"successfully processed forecast for {forecast_date}-{accumulation}-{time}")


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
            print(f"start date defaulting to 2 days since today -> {start_dt}")

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
            print(f"final date defaulting to today -> {final_date}")
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
    start_date: str | None = None,
    final_date: str | None = None,
    accumulation: Literal["6h", "24h"] | None = "6h",
    time: Literal["0000", "0600", "1200", "1800"] | None = "0000",
    days_to_check: int | None = 2,
    delete_forecasts: Literal["Y", "N"] | None = "Y",
) -> None:
    print(
        f"received request to autogenerate forecasts from {start_date} to {final_date} with "
        + f"accumulation {accumulation} and initialization time {time}"
    )
    forecast_dates = forecast_dates_generator(
        start_date=start_date, final_date=final_date, days_to_check=days_to_check
    )
    print(f"starting forecasts generation for {' => '.join(forecast_dates)}")
    for forecast_date in forecast_dates:
        gen_forecast_request(
            **{
                "delete_forecasts": delete_forecasts,
                "forecast_date": forecast_date,
                "accumulation": accumulation,
                "time": time,
            }
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""
        Function: Autogenerate cGAN forecasts from specified start date to final date. All parameters are optional and can be ommited.

        Arguments:
            --start_date     - generate forecasts starting from this date. By defaults, the program uses 30 days from the date today.
            --final_date     - generate forecasts from start_date to this date. By default, the program uses the date today.
            --days_to_check  - number of forecasts days to be checked since today. Can be used to dynamically generate start_date and final_date.
            --accumulation   - forecast accumulation period. Either of 6h or 24h. The program uses 6h by default
            --time           - forecast initialization time. Either of 0000, 0600, 1200 or 1800. The program uses 0000 by default
        
        Returns:
            A list of successfully generated forecasts
        """,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--start_date",
        help="Forecasts generation start date in format (YYMMDD)",
        default=None,
        type=str,
    )
    parser.add_argument(
        "--final_date",
        help="Forecasts generation start date in format (YYMMDD)",
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
        help="How long rainfall is accumulated for, either 6h or 24h",
        default="6h",
        type=str,
    )
    parser.add_argument(
        "--time", help="Forecast initialisation time (HHMM)", default="0000", type=str
    )
    parser.add_argument(
        "--delete_forecasts",
        help="Should forecasts be deleted or not (Y/N)",
        default=None,
        type=str,
    )
    args = parser.parse_args()
    auto_gen_forecasts(
        start_date=args.start_date,
        final_date=args.final_date,
        time=args.time,
        accumulation=args.accumulation,
        days_to_check=args.days_to_check,
        delete_forecasts=args.delete_forecasts,
    )
