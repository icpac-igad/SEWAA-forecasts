#!/usr/bin/env python3
"""
Purpose: Build the admin-1 boundary .json files drawn by the forecast viewer for
         Somalia, Uganda, Eritrea and Ethiopia, and keep the viewer's index files in sync.
Inputs:
    shapes/Somalia_shapes/geoBoundaries-SOM-ADM1.geojson   (geoBoundaries gbOpen, OSM, ODbL 1.0)
    shapes/Uganda_shapes/Uganda_region.shp                 (Who's On First, 111 districts)
    shapes/Eritrea_shapes/Eritrea_region.shp               (Who's On First, 6 regions)
    shapes/Ethiopia_shapes/eth_adm_csa_bofedb_2021_shp/eth_admbnda_adm1_csa_bofedb_2021.shp (OCHA COD-AB)
Outputs (in interface/static/boundaries/):
    {Country}/{Region}_boundary.json   one file per admin-1 unit
    regional_names.json                region list per country (drives which files are loaded)
    region_bboxes.json                 region names and extents (drives the Admin 1 dropdown)
Dependencies: geopandas, shapely

Run shapes/simplify_boundaries.py afterwards to shrink the new files.
Country border files ({Country}_border.json) are not touched.

Usage:
    python shapes/build_admin1_boundaries.py
"""

import json
import logging
import math
from pathlib import Path

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SHAPES_DIR = Path(__file__).resolve().parent
OUT_DIR = SHAPES_DIR.parent / "interface" / "static" / "boundaries"

# Forecast grid used for the lat_idx / lon_idx fields (0.1 deg, same as the existing files).
GRID_LON0, GRID_LAT0, GRID_STEP = 19.15, -13.65, 0.1

# Eritrea_region.shp has a wrong "name" column (e.g. Northern Red Sea is labelled "Debub");
# its ISO codes are correct, so names are assigned from those.
ERITREA_NAMES = {
    "ER-AN": "Anseba",
    "ER-DU": "Debub",
    "ER-DK": "Debubawi Keyih Bahri",
    "ER-GB": "Gash Barka",
    "ER-MA": "Maekel",
    "ER-SK": "Semenawi Keyih Bahri",
}


def load_somalia():
    gdf = gpd.read_file(SHAPES_DIR / "Somalia_shapes" / "geoBoundaries-SOM-ADM1.geojson")
    return gdf.assign(region=gdf["shapeName"])


def load_uganda():
    gdf = gpd.read_file(SHAPES_DIR / "Uganda_shapes" / "Uganda_region.shp", encoding="latin1")
    return gdf.assign(region=gdf["name"])


def load_eritrea():
    gdf = gpd.read_file(SHAPES_DIR / "Eritrea_shapes" / "Eritrea_region.shp")
    return gdf.assign(region=gdf["iso_code"].map(ERITREA_NAMES))


def load_ethiopia():
    path = SHAPES_DIR / "Ethiopia_shapes" / "eth_adm_csa_bofedb_2021_shp" / "eth_admbnda_adm1_csa_bofedb_2021.shp"
    gdf = gpd.read_file(path)
    return gdf.assign(region=gdf["ADM1_EN"])


SOURCES = {
    "Somalia": load_somalia,
    "Uganda": load_uganda,
    "Eritrea": load_eritrea,
    "Ethiopia": load_ethiopia,
}


def grid_indices(lo, hi, origin):
    """Grid cells just outside [lo, hi], matching the convention of the existing files."""
    return [max(0, math.floor((lo - origin) / GRID_STEP)), math.floor((hi - origin) / GRID_STEP) + 1]


def geometry_lines(geom):
    """All polygon rings as [xs, ys] segments."""
    polygons = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    lines = []
    for poly in polygons:
        if not isinstance(poly, Polygon) or poly.is_empty:
            continue
        for ring in [poly.exterior, *poly.interiors]:
            xs, ys = ring.xy
            lines.append([list(xs), list(ys)])
    return lines


def region_json(name, geom):
    min_lon, min_lat, max_lon, max_lat = geom.bounds
    return {
        "name": name,
        "bounding_box": [min_lon, min_lat, max_lon, max_lat],
        "lat_idx": grid_indices(min_lat, max_lat, GRID_LAT0),
        "lon_idx": grid_indices(min_lon, max_lon, GRID_LON0),
        "line": geometry_lines(geom),
    }


def validate(gdf, country):
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    if gdf["region"].isna().any():
        raise ValueError(f"{country}: unnamed regions in source")
    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        logger.info(f"{country}: fixing {invalid.sum()} invalid geometries with buffer(0)")
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].buffer(0)
    # Merge any regions split over several rows into one geometry
    return gdf.dissolve(by="region", as_index=False)


def main():
    names_path = OUT_DIR / "regional_names.json"
    bboxes_path = OUT_DIR / "region_bboxes.json"
    regional_names = json.loads(names_path.read_text())
    region_bboxes = json.loads(bboxes_path.read_text())

    for country, loader in SOURCES.items():
        gdf = validate(loader(), country)
        country_dir = OUT_DIR / country
        entry = next(e for e in regional_names if e["country"] == country)

        # Remove region files from the previous build (the country border is kept)
        for old in entry["region"]:
            path = country_dir / f"{old}_boundary.json"
            if path.exists():
                path.unlink()

        regions = sorted(gdf["region"])
        for row in gdf.itertuples():
            data = region_json(row.region, row.geometry)
            (country_dir / f"{row.region}_boundary.json").write_text(json.dumps(data, separators=(",", ":")))

        entry["region"] = regions
        region_bboxes[country] = [
            {"name": row.region, "bbox": [round(v, 4) for v in row.geometry.bounds]}
            for row in gdf.sort_values("region").itertuples()
        ]
        logger.info(f"{country}: wrote {len(regions)} admin-1 boundaries")

    names_path.write_text(json.dumps(regional_names))
    bboxes_path.write_text(json.dumps(region_bboxes))
    logger.info("Updated regional_names.json and region_bboxes.json")


if __name__ == "__main__":
    main()
