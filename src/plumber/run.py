"""Read ./plumber.yaml, resolve the user's functions, and hand them to a strategy."""

import warnings
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


def build_step(entry, overrides):
    """Build one Step. CLI overrides replace config params, key by key (shallow merge).

    An override only applies to phases that already list that key in their params.
    """
    params = entry.get("params") or {}
    params = {key: overrides.get(key, value) for key, value in params.items()}
    return Step(
        name=entry.get("name", entry["path"]),
        fn=resolve(entry["path"]),
        params=params,
        partitionable=entry["partitionable"],
        checkpoint=entry.get("checkpoint", False),
    )


def build_steps(config, overrides):
    """Build every Step in config order. Names must be unique; overrides must match a phase."""
    entries = config["phases"]
    first_seen = {}
    for number, entry in enumerate(entries, start=1):
        name = entry.get("name", entry["path"])
        if name in first_seen:
            raise ValueError(
                f"Duplicate phase name {name!r}: entries {first_seen[name]} and {number}. "
                "Give each a distinct `name:`."
            )
        first_seen[name] = number

    known = {key for entry in entries for key in (entry.get("params") or {})}
    unused = sorted(set(overrides) - known)
    if unused:
        raise ValueError(f"--params {', '.join(unused)}: no phase has a param with that name")

    return [build_step(entry, overrides) for entry in entries]


def run(config, overrides=None):
    """Run the pipeline. This never reads data; the strategy calls the user's functions."""
    input_pair = bind(config["input"])
    steps = build_steps(config, overrides or {})
    if config.get("output"):
        output_pair = bind(config["output"])
    else:
        warnings.warn("No `output:` in config: result discarded", stacklevel=2)
        output_pair = None
    return LocalSequential().execute(input_pair, steps, output_pair, {})
