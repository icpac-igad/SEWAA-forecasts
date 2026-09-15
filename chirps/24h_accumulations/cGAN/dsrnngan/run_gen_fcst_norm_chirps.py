"""Generate FCSTNorm2018.pkl for the CHIRPS run.

Replaces run_gen_fcst_norm.py, which carried a hardcoded Windows sys.path and
silently failed when invoked from the repo root. This version resolves imports
relative to its own location, logs each field as it completes, and lets any
traceback propagate so stderr actually shows the cause.
"""
import os
import pickle
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import data  # noqa: E402

YEAR = 2018


def main():
    stats_dic = {}
    fcstnorm_path = os.path.join(data.NORMALISATION_PATH, f"FCSTNorm{YEAR}.pkl")
    print(f"writing to {fcstnorm_path}", flush=True)

    # fail fast if the destination isn't writable, before doing 98GB of IO
    with open(fcstnorm_path, "wb") as f:
        pickle.dump(stats_dic, f)

    t_start = time.time()
    for i, field in enumerate(data.all_fcst_fields, 1):
        t0 = time.time()
        mi, mx, mn, sd = data.get_fcst_stats_fast(field, YEAR)
        stats_dic[field] = {"min": mi, "max": mx, "mean": mn, "std": sd}
        print(
            f"[{i:2d}/{len(data.all_fcst_fields)}] {field:6s} "
            f"min={mi:12.4g} max={mx:12.4g} mean={mn:12.4g} std={sd:12.4g} "
            f"({time.time() - t0:.0f}s)",
            flush=True,
        )
        # checkpoint after every field so a late crash doesn't lose the lot
        with open(fcstnorm_path, "wb") as f:
            pickle.dump(stats_dic, f)

    print(f"done: {len(stats_dic)} fields in {time.time() - t_start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
