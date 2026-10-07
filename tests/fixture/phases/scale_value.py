"""Partitionable, has params: multiply `value` by `factor`."""


def run(gdf, factor=1, **params):
    gdf = gdf.copy()
    gdf["value"] = gdf["value"] * factor
    return gdf
