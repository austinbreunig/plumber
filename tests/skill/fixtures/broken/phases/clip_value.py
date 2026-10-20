"""Needs a `limit` param and takes no extra params."""


def run(gdf, limit):
    return gdf[gdf["value"] <= limit]
