"""Read ./plumber.yaml, resolve the user's functions, and hand them to a strategy."""

from pathlib import Path

import yaml

from plumber.local import LocalSequential
from plumber.protocols import Step
from plumber.resolver import resolve


def load_config(path="plumber.yaml"):
    return yaml.safe_load(Path(path).read_text())


def bind(entry):
    """Turn an `input:`/`output:` block into a (function, params) pair."""
    return resolve(entry["path"]), entry.get("params") or {}


def build_step(entry):
    return Step(
        name=entry.get("name", entry["path"]),
        fn=resolve(entry["path"]),
        params=entry.get("params") or {},
        partitionable=entry["partitionable"],
        checkpoint=entry.get("checkpoint", False),
    )


def run(config):
    """Run the pipeline. This never reads data; the strategy calls the user's functions."""
    input_pair = bind(config["input"])
    steps = [build_step(entry) for entry in config["phases"]]
    output_pair = bind(config["output"]) if config.get("output") else None
    return LocalSequential().execute(input_pair, steps, output_pair, {})
