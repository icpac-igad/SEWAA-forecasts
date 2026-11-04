#!/usr/bin/env python3
"""
Purpose: Shrink the boundary .json files drawn by the forecast viewer so maps load fast.
Inputs: interface/static/boundaries/**/*.json (output of ExtractJSON.ipynb).
Outputs: The same files, rewritten in place with simplified lines and rounded coordinates.
Dependencies: none (standard library only)

Each line segment is simplified with Douglas-Peucker and coordinates are rounded.
Segment end points are always kept, so neighbouring regions still meet.
The default tolerance (0.002 deg, ~200 m) is far below what is visible at the
forecast grid resolution (0.1 deg). Running the script again is safe.

Usage:
    python shapes/simplify_boundaries.py [--tolerance 0.002] [--decimals 4] [--dir PATH]
"""

import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "interface" / "static" / "boundaries"


def douglas_peucker(xs, ys, tolerance):
    """Return the indices of the points kept by Douglas-Peucker simplification."""
    n = len(xs)
    if n < 3:
        return list(range(n))
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    tol2 = tolerance * tolerance
    while stack:
        start, end = stack.pop()
        x0, y0, x1, y1 = xs[start], ys[start], xs[end], ys[end]
        dx, dy = x1 - x0, y1 - y0
        seg2 = dx * dx + dy * dy
        max_d2, max_i = -1.0, -1
        for i in range(start + 1, end):
            px, py = xs[i] - x0, ys[i] - y0
            if seg2 == 0:
                d2 = px * px + py * py
            else:
                t = max(0.0, min(1.0, (px * dx + py * dy) / seg2))
                ex, ey = px - t * dx, py - t * dy
                d2 = ex * ex + ey * ey
            if d2 > max_d2:
                max_d2, max_i = d2, i
        if max_d2 > tol2:
            keep[max_i] = True
            stack.append((start, max_i))
            stack.append((max_i, end))
    return [i for i in range(n) if keep[i]]


def simplify_lines(lines, tolerance, decimals):
    """Simplify a list of [xs, ys] segments."""
    out = []
    for xs, ys in lines:
        idx = douglas_peucker(xs, ys, tolerance)
        out.append([[round(xs[i], decimals) for i in idx], [round(ys[i], decimals) for i in idx]])
    return out


def simplify_feature(feature, tolerance, decimals):
    if isinstance(feature, dict) and "line" in feature:
        feature["line"] = simplify_lines(feature["line"], tolerance, decimals)
    return feature


def count_points(data):
    features = data if isinstance(data, list) else [data]
    return sum(len(seg[0]) for f in features if isinstance(f, dict) for seg in f.get("line", []))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="boundaries directory")
    parser.add_argument("--tolerance", type=float, default=0.002, help="simplification tolerance in degrees")
    parser.add_argument("--decimals", type=int, default=4, help="decimal places kept in coordinates")
    args = parser.parse_args()

    total_before = total_after = 0
    for path in sorted(args.dir.rglob("*.json")):
        before = path.stat().st_size
        data = json.loads(path.read_text())
        points_before = count_points(data)
        if points_before == 0:
            continue  # index files such as regional_names.json / region_bboxes.json
        if isinstance(data, list):
            data = [simplify_feature(f, args.tolerance, args.decimals) for f in data]
        else:
            data = simplify_feature(data, args.tolerance, args.decimals)
        path.write_text(json.dumps(data, separators=(",", ":")))
        after = path.stat().st_size
        total_before += before
        total_after += after
        logger.info(
            f"{path.relative_to(args.dir)}: {points_before} -> {count_points(data)} points, "
            f"{before / 1024:.0f} -> {after / 1024:.0f} KB"
        )

    if total_before:
        logger.info(
            f"Total: {total_before / 1e6:.2f} -> {total_after / 1e6:.2f} MB "
            f"({100 * (1 - total_after / total_before):.0f}% smaller)"
        )


if __name__ == "__main__":
    main()
