"""Input and output functions for the deliberately broken fixture."""

import geopandas as gpd
from shapely.geometry import Point


def load_fixture():
    rows = [{"id": i, "value": i, "geometry": Point(i, i)} for i in range(12)]
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def write_parquet(gdf, path):
    gdf.to_parquet(path)
