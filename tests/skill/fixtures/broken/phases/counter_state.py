"""Keeps hidden state: the same input gives a different output each call."""

calls = []


def run(gdf, **params):
    calls.append(1)
    gdf = gdf.copy()
    gdf["n"] = len(calls)
    return gdf
