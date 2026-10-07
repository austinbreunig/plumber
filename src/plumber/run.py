"""Read ./plumber.yaml, resolve the user's functions, and hand them to a strategy."""

import warnings
from pathlib import Path

import yaml

from plumber.local import LocalSequential
from plumber.protocols import Step
from plumber.resolver import resolve


def load_config(path="plumber.yaml"):
    return yaml.safe_load(Path(path).read_text())


def params_of(entry):
    return entry.get("params") or {}


def name_of(entry):
    return entry.get("name", entry["path"])


def bind(entry):
    """Turn an `input:`/`output:` block into a (function, params) pair."""
    return resolve(entry["path"]), params_of(entry)


def build_step(entry, overrides):
    """Build one Step. CLI overrides replace config params, key by key (shallow merge).

    An override only applies to phases that already list that key in their params.
    """
    params = params_of(entry)
    params = {key: overrides.get(key, value) for key, value in params.items()}
    return Step(
        name=name_of(entry),
        fn=resolve(entry["path"]),
        params=params,
        partitionable=entry["partitionable"],
        checkpoint=entry.get("checkpoint", False),
    )


def build_steps(config, overrides):
    """Build every Step in config order. Names must be unique.

    Warns about `--params` keys that no phase lists (likely typos).
    """
    entries = config["phases"]
    first_seen = {}
    for number, entry in enumerate(entries, start=1):
        name = name_of(entry)
        if name in first_seen:
            raise ValueError(
                f"Duplicate phase name {name!r}: entries {first_seen[name]} and {number}. "
                "Give each a distinct `name:`."
            )
        first_seen[name] = number

    listed = {key for entry in entries for key in params_of(entry)}
    for key in overrides:
        if key not in listed:
            warnings.warn(f"--params {key}: no phase lists this param, so it was ignored")

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
