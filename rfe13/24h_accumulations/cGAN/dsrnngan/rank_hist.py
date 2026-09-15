"""Rank histogram diagnostics for the RFE2 cGAN runs.

Ranks are stored normalised (0..1) with ensemble_size=10, so there are exactly
11 attainable values. Binning at the plots.py default of N_ranks=101 aliases
them; we bin at 11, one bin per attainable rank.
"""
import glob
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

LOGDIR = "/home/ezra/SEWAA-forecasts-RFE2/SEWAA-forecasts/24h_accumulations/cGAN"
OUT = os.path.join(LOGDIR, "rank_histogram_diagnostics.png")

ENS = 10                      # ensemble_size used at eval time
NB = ENS + 1                  # 11 attainable ranks
UNIFORM = 1.0 / NB
CENTRES = np.arange(NB) / ENS

# --- palette (dataviz reference instance, light mode; validated) -------------
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"   # categorical slots 1-3
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"


def final_rank_file(run):
    """Newest checkpoint's rank file for a run, or None."""
    hits = glob.glob(os.path.join(LOGDIR, f"logs_RFE2_{run}", "ranksnew-*.npz"))
    if not hits:
        return None
    return max(hits, key=lambda p: int(re.search(r"-(\d+)\.npz$", p).group(1)))


def freq(ranks):
    """Frequency per attainable rank."""
    idx = (ranks * ENS).round().astype(np.int8)
    return np.bincount(idx, minlength=NB) / len(idx)


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(BASELINE)
        ax.spines[s].set_linewidth(1.0)
    ax.tick_params(colors=MUTED, labelsize=8.5, length=3, width=0.8)
    ax.set_xticks(CENTRES)
    ax.set_xticklabels([f"{i}" for i in range(NB)])


def uniform_ref(ax):
    ax.axhline(UNIFORM, ls=":", lw=1.2, color=MUTED, zorder=1)


fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.9))
fig.patch.set_facecolor(SURFACE)
table_rows = []

# ---------------------------------------------------------------- panel A ---
ax = axes[0]
f11 = np.load(final_rank_file("run11"))
r11, lo11 = f11["ranks"], f11["lowres"]
h11 = freq(r11)

ax.bar(CENTRES, h11, width=0.072, color=S1, zorder=3)
uniform_ref(ax)
style(ax)
ax.set_ylim(0, max(h11) * 1.28)
ax.set_xlabel("Rank of truth within the 10-member ensemble", color=INK2, fontsize=9.5)
ax.set_ylabel("Frequency", color=INK2, fontsize=9.5)
ax.set_title("run11, all grid points\nU-shape = ensemble too narrow",
             color=INK, fontsize=11, loc="left", pad=10)
for x, v in ((CENTRES[0], h11[0]), (CENTRES[-1], h11[-1])):
    ax.annotate(f"{v:.3f}", (x, v), textcoords="offset points", xytext=(0, 5),
                ha="center", fontsize=8.5, color=INK)
ax.annotate("uniform = 0.091", (0.5, UNIFORM), textcoords="offset points",
            xytext=(0, 7), ha="center", fontsize=8.5, color=MUTED)
table_rows.append(("run11 · all points", h11, len(r11)))

# ---------------------------------------------------------------- panel B ---
# Stratify on the FORECAST field (lowres), not the truth: conditioning a rank
# histogram on the observation biases it. Matches thresholded_ranks.findthresh.
ax = axes[1]
strata = [
    ("dry (<0.02 mm/day)",   lo11 <= 0.001,                      MUTED, "--"),
    ("light (0.02-1.2)",     (lo11 > 0.001) & (lo11 <= 0.05),    S1,    "-"),
    ("moderate (1.2-3.6)",   (lo11 > 0.05) & (lo11 <= 0.15),     S2,    "-"),
    ("heavy (>3.6 mm/day)",  lo11 > 0.15,                        S3,    "-"),
]
for label, mask, colour, ls in strata:
    sub = r11[mask]
    h = freq(sub)
    ax.plot(CENTRES, h, ls=ls, lw=2.0, color=colour, marker="o", ms=5.5,
            label=f"{label}  n={mask.sum()/1e6:.1f}M", zorder=3,
            markeredgecolor=SURFACE, markeredgewidth=1.2)
    table_rows.append((f"run11 · {label}", h, int(mask.sum())))
uniform_ref(ax)
style(ax)
ax.set_xlabel("Rank of truth within the 10-member ensemble", color=INK2, fontsize=9.5)
ax.set_title("run11 by forecast rain rate\nthe deficit is in the raining points",
             color=INK, fontsize=11, loc="left", pad=10)
leg = ax.legend(frameon=False, fontsize=8.2, loc="upper center", ncol=1)
for t in leg.get_texts():
    t.set_color(INK2)

del r11, lo11, f11

# ---------------------------------------------------------------- panel C ---
ax = axes[2]
for run, colour in (("run09", S1), ("run10", S2), ("run11", S3)):
    p = final_rank_file(run)
    if p is None:
        continue
    fr = np.load(p)
    h = freq(fr["ranks"])
    step = int(re.search(r"-(\d+)\.npz$", p).group(1))
    ax.plot(CENTRES, h, lw=2.0, color=colour, marker="o", ms=5.5,
            label=f"{run} @ {step//1000}k", zorder=3,
            markeredgecolor=SURFACE, markeredgewidth=1.2)
    table_rows.append((f"{run} @ {step} · all points", h, len(fr["ranks"])))
    del fr
uniform_ref(ax)
style(ax)
ax.set_xlabel("Rank of truth within the 10-member ensemble", color=INK2, fontsize=9.5)
ax.set_title("across runs, all grid points\nunder-dispersion is not improving",
             color=INK, fontsize=11, loc="left", pad=10)
leg = ax.legend(frameon=False, fontsize=8.5, loc="upper center")
for t in leg.get_texts():
    t.set_color(INK2)

fig.suptitle("RFE2 cGAN rank histograms — 11 bins (ensemble_size=10), validation year 2020",
             color=INK, fontsize=12.5, x=0.006, ha="left", y=0.99)
fig.tight_layout(rect=(0, 0, 1, 0.93))
fig.savefig(OUT, dpi=170, facecolor=SURFACE)
print("wrote", OUT)

# ------------------------------------------------------- table view (relief) -
print("\n" + "=" * 104)
print("TABLE VIEW — frequency per rank (uniform = 0.0909)")
print("=" * 104)
print(f"{'series':<34}{'n':>11}  " + "".join(f"{i:>6}" for i in range(NB)))
print("-" * 104)
for name, h, n in table_rows:
    print(f"{name:<34}{n:>11,}  " + "".join(f"{v:>6.3f}" for v in h))

print("\n" + "=" * 104)
print("DISPERSION DIAGNOSTICS")
print("=" * 104)
print(f"{'series':<34}{'OPL':>8}{'OPR':>8}{'ends/unif':>11}{'middle/unif':>13}{'reliability dev':>17}")
print("-" * 104)
for name, h, n in table_rows:
    ends = (h[0] + h[-1]) / (2 * UNIFORM)
    mid = h[3:8].mean() / UNIFORM
    dev = np.abs(h - UNIFORM).sum()
    print(f"{name:<34}{h[0]:>8.3f}{h[-1]:>8.3f}{ends:>11.2f}{mid:>13.2f}{dev:>17.3f}")
print("\nOPL = frequency truth below every member (over-forecast)")
print("OPR = frequency truth above every member (under-forecast)")
print("ends/unif > 1 and middle/unif < 1  =>  under-dispersed")
