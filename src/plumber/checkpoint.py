"""Checkpoints: a phase's output saved as GeoParquet. Plumber writes these itself."""

from pathlib import Path

import geopandas as gpd

DEFAULT_DIR = "./.plumber/checkpoints"


def checkpoint_dir(run_params):
    """The folder checkpoints go in, from the strategy's `run_params`."""
    return run_params.get("checkpoint_dir", DEFAULT_DIR)


def checkpoint_path(directory, name):
    return Path(directory) / f"{name}.parquet"


def write_checkpoint(data, directory, name):
    """Save `data` to `<directory>/<name>.parquet`, replacing any old file."""
    path = checkpoint_path(directory, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    data.to_parquet(path)


def read_checkpoint(directory, name):
    return gpd.read_parquet(checkpoint_path(directory, name))
