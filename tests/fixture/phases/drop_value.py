"""Drops a column."""


def run(gdf, **params):
    return gdf.drop(columns=["value"])
