"""Partitionable, has params: multiply `value` by `factor`."""

import logging

log = logging.getLogger(__name__)


def run(gdf, factor=1, **params):
    log.info("scaling by %s", factor)
    gdf = gdf.copy()
    gdf["value"] = gdf["value"] * factor
    return gdf
