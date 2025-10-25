from typing import Literal
from pandas import date_range
import argparse
import threading
import subprocess
from datetime import datetime, timedelta


def make_gen_forecast_request(
    forecast_date: str,
    accumulation: Literal["6h", "24h"] | None = "6h",
    time: Literal["0000", "0600", "1200", "1800"] | None = "0000",
) -> bool:
    accumulation = accumulation if accumulation is not None else "6h"
    time = time if time is not None else "0000"
    params = [
        "python",
        "run_forecast.py",
        "--delete_forecasts",
        "Y",
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
    start_date: str | None = None, final_date: str | None = None
) -> list[str]:
    if start_date is None:
        start_date = datetime.today() - timedelta(days=30)
    else:
        try:
            start_date = datetime.strptime(start_date, "%Y%m%d").date()
        except Exception as err:
            print(
                f"failed to parse start date parameter {start_date} to a valid date object with error {err}"
            )
            start_date = datetime.today() - timedelta(days=30)
            print(f"start date defaulting to 30 days since today -> {start_date}")

    if final_date is None:
        final_date = datetime.today().date()
    else:
        try:
            final_date = datetime.strptime(final_date, "%Y%m%d").date()
        except Exception as err:
            print(
                f"failed to parse final date parameter {final_date} to a valid date object with error {err}"
            )
            final_date = datetime.today()
            print(f"final date defaulting to today -> {final_date}")
    return [
        dt.strftime("%Y%m%d")
        for dt in date_range(start=start_date, end=final_date, freq="D")
    ]


def auto_gen_forecasts(
    start_date: str | None = None,
    final_date: str | None = None,
    accumulation: Literal["6h", "24h"] | None = "6h",
    time: Literal["0000", "0600", "1200", "1800"] | None = "0000",
) -> None:
    print(
        f"received request to autogenerate forecasts from {start_date} to {final_date} with "
        + f"accumulation {accumulation} and initialization time {time}"
    )
    forecast_dates = forecast_dates_generator(
        start_date=start_date, final_date=final_date
    )
    print(f"starting forecasts generation for {' => '.join(forecast_dates)}")
    for forecast_date in forecast_dates:
        worker = threading.Thread(
            target=make_gen_forecast_request,
            kwargs={
                "forecast_date": forecast_date,
                "accumulation": accumulation,
                "time": time,
            },
            name=f"{forecast_date}-{accumulation}-{time}",
        )
        worker.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""
        Function: Autogenerate cGAN forecasts from specified start date to final date. All parameters are optional and can be ommited.

        Arguments:
            --start_date     - generate forecasts starting from this date. By defaults, the program uses 30 days from the date today.
            --final_date     - generate forecasts from start_date to this date. By default, the program uses the date today.
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
        "--accumulation",
        help="How long rainfall is accumulated for, either 6h or 24h",
        default="6h",
        type=str,
    )
    parser.add_argument(
        "--time", help="Forecast initialisation time (HHMM)", default="0000", type=str
    )
    args = parser.parse_args()
    auto_gen_forecasts(
        start_date=args.start_date,
        final_date=args.final_date,
        time=args.time,
        accumulation=args.accumulation,
    )
