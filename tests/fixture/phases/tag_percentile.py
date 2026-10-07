"""Partitionable, has params: flag rows whose `value` is above `threshold`."""


def run(gdf, threshold=10, **params):
    gdf = gdf.copy()
    gdf["high"] = gdf["value"] > threshold
    return gdf
