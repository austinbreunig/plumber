"""The user's own input and output functions for the tracer fixture."""

from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point


def load_fixture():
    """12 rows in 3 zones (A/B/C) of 4 rows each. Not sorted by zone on purpose."""
    zones = ["A", "B", "C"]
    rows = [
        {"id": i, "zone": zones[(i * 5) % 3], "value": (i * 7) % 20, "geometry": Point(i, i)}
        for i in range(12)
    ]
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def write_parquet(gdf, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(path)
