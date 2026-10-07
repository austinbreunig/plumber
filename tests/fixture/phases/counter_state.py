"""Partitionable but keeps state in a global: the second call on the same input differs."""

calls = []


def run(gdf, **params):
    calls.append(1)
    gdf = gdf.copy()
    gdf["value"] = gdf["value"] + len(calls)
    return gdf
