#!/usr/bin/env python
"""Quick-look plot of a cGAN-RFE forecast .nc file.

Usage:
    python plot_forecast.py <GAN_fcst_crps_YYYYMMDD_00Z.nc>            # ensemble-mean, all 7 leads
    python plot_forecast.py <file.nc> --lead 0                        # one lead (0 = D+1)
    python plot_forecast.py <file.nc> --lead 0 --member 3             # a single member

Output: saves a PNG next to the .nc file. precipitation is mm/h in the file; shown as mm/day.
"""
import argparse, os
import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")                     # save to file, no display needed
import matplotlib.pyplot as plt

LEAD_LABELS = ["D+1", "D+2", "D+3", "D+4", "D+5", "D+6", "D+7"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ncfile")
    ap.add_argument("--lead", type=int, default=None, help="valid_time index (0=D+1). Omit = all leads")
    ap.add_argument("--member", type=int, default=None, help="member index; omit = ensemble mean")
    a = ap.parse_args()

    d = xr.open_dataset(a.ncfile)
    p = d["precipitation"]                                   # (time, valid_time, member, lat, lon) or similar
    lat, lon = d["latitude"].values, d["longitude"].values
    # collapse the singleton 'time' dim if present
    p = p.squeeze("time", drop=True) if "time" in p.dims and d.sizes.get("time",1)==1 else p

    def field(lead):
        f = p.isel(valid_time=lead)
        f = f.isel(member=a.member) if a.member is not None else f.mean("member")
        return f.values * 24.0                               # mm/h -> mm/day

    extent = [lon.min(), lon.max(), lat.min(), lat.max()]
    who = f"member {a.member}" if a.member is not None else "ensemble mean"
    base = os.path.splitext(os.path.basename(a.ncfile))[0]

    if a.lead is not None:
        arr = field(a.lead)
        plt.figure(figsize=(7,7))
        im = plt.imshow(arr, origin="lower", extent=extent, cmap="Blues",
                        vmin=0, vmax=max(5, np.percentile(arr,99.5)))
        plt.colorbar(im, label="rainfall (mm/day)", shrink=0.8)
        plt.title(f"{base}\n{LEAD_LABELS[a.lead]}  ({who})")
        plt.xlabel("longitude"); plt.ylabel("latitude")
        out = f"{os.path.splitext(a.ncfile)[0]}_lead{a.lead}.png"
    else:
        n = p.sizes["valid_time"]
        vmax = max(5, np.percentile(field(0), 99.5))
        fig, axes = plt.subplots(2, 4, figsize=(18,9))
        for i, ax in enumerate(axes.flat):
            if i >= n: ax.axis("off"); continue
            im = ax.imshow(field(i), origin="lower", extent=extent, cmap="Blues", vmin=0, vmax=vmax)
            ax.set_title(f"{LEAD_LABELS[i]}"); ax.set_xticks([]); ax.set_yticks([])
        fig.colorbar(im, ax=axes.ravel().tolist(), label="rainfall (mm/day)", shrink=0.6)
        fig.suptitle(f"{base}  ({who})", fontsize=14)
        out = f"{os.path.splitext(a.ncfile)[0]}_allleads.png"

    plt.savefig(out, dpi=110, bbox_inches="tight")
    print(f"saved {out}")

if __name__ == "__main__":
    main()
