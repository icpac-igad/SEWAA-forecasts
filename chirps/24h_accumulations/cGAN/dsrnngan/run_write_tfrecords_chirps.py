"""Write the CHIRPS tfrecords for train (2018-2020) and val (2021).

Resolves imports relative to its own location so it can be run from anywhere,
and lets tracebacks propagate to stderr.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import read_config  # noqa: E402
import tfrecords_generator  # noqa: E402

YEARS = [2018, 2019, 2020, 2021]


def main():
    folder = read_config.get_data_paths()["TFRecords"]["tfrecords_path"]
    os.makedirs(folder, exist_ok=True)
    print(f"writing tfrecords to {folder}", flush=True)

    t_start = time.time()
    for year in YEARS:
        t0 = time.time()
        print(f"\n=== {year} ===", flush=True)
        tfrecords_generator.write_data(year, folder=folder)
        print(f"=== {year} done in {time.time() - t0:.0f}s ===", flush=True)

    print(f"\nall years done in {time.time() - t_start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
