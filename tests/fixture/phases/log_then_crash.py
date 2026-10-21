"""Partitionable. Logs a line, then always raises."""

import logging

log = logging.getLogger(__name__)


def run(gdf, **params):
    log.info("about to crash")
    raise RuntimeError("boom")
