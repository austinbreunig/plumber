"""Read ./plumber.yaml, resolve the user's functions, and hand them to a strategy."""

import time
import warnings
from pathlib import Path

import yaml

from plumber.check import DEFAULT_STRATEGY, preflight
from plumber.checkpoint import DEFAULT_DIR, checkpoint_path, read_checkpoint
from plumber.entries import merge_params, name_of, params_of
from plumber.local import LocalSequential
from plumber.localmp import LocalMultiprocess
from plumber.protocols import Step, plumber_log
from plumber.resolver import resolve


def load_config(path="plumber.yaml"):
    return yaml.safe_load(Path(path).read_text())


def bind(entry):
    """Turn an `input:`/`output:` block into a (function, params) pair."""
    return resolve(entry["path"]), params_of(entry)


def build_step(entry, overrides):
    """Build one Step, with CLI overrides merged into its params."""
    return Step(
        name=name_of(entry),
        fn=resolve(entry["path"]),
        params=merge_params(entry, overrides),
        partitionable=entry["partitionable"],
        checkpoint=entry.get("checkpoint", False),
    )


def build_steps(config, overrides):
    """Build every Step in config order. `preflight` has already vetted the names."""
    return [build_step(entry, overrides) for entry in config["phases"]]


def build_strategy(config):
    """Pick the execution strategy from `execution:` (default `local`); `check` vetted it."""
    execution = config.get("execution") or {}
    if execution.get("strategy", DEFAULT_STRATEGY) == "localmp":
        return LocalMultiprocess(execution["partition"])
    return LocalSequential()


def phase_index(steps, name, flag):
    names = [step.name for step in steps]
    if name not in names:
        raise SystemExit(f"{flag} {name}: no such phase. Phases are: {', '.join(names)}")
    return names.index(name)


def checkpoint_input(steps, first, directory):
    """The input pair for `--from`: read the checkpoint of the phase before `first`."""
    previous = steps[first - 1].name
    path = checkpoint_path(directory, previous)
    if not path.exists():
        raise SystemExit(
            f"--from {steps[first].name}: no checkpoint for {previous!r} at {path}. "
            f"Set `checkpoint: true` on {previous} and run through it once."
        )
    saved = time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime))
    warnings.warn(
        f"Starting at {steps[first].name} from checkpoint {path.name} (saved {saved})",
        stacklevel=3,
    )
    return read_checkpoint, {"directory": directory, "name": previous}


def run(config, overrides=None, start=None, stop=None):
    """Run the pipeline. This never reads data; the strategy calls the user's functions.

    `start`/`stop` are phase names (`--from`/`--to`). This function alone rewrites the call:
    a later `start` swaps the input for the previous checkpoint, and an earlier `stop`
    drops the output. The strategy just gets an ordinary `execute`.
    """
    overrides = overrides or {}
    preflight(config, overrides)
    input_pair = bind(config["input"])
    all_steps = build_steps(config, overrides)
    if config.get("output"):
        output_pair = bind(config["output"])
    else:
        warnings.warn("No `output:` in config: result discarded", stacklevel=2)
        output_pair = None
    directory = (config.get("checkpoints") or {}).get("dir", DEFAULT_DIR)

    first = phase_index(all_steps, start, "--from") if start else 0
    last = phase_index(all_steps, stop, "--to") if stop else len(all_steps) - 1
    if first > last:
        raise SystemExit(f"--from {start} comes after --to {stop}")
    if first > 0:
        input_pair = checkpoint_input(all_steps, first, directory)
    if last < len(all_steps) - 1:
        output_pair = None
        if not all_steps[last].checkpoint:
            warnings.warn(
                f"--to {stop}: {stop} has no checkpoint: result discarded; runs anyway",
                stacklevel=2,
            )
    steps = all_steps[first : last + 1]
    run_params = {"checkpoint_dir": directory}
    if "user_level" in config:
        run_params["user_level"] = config["user_level"]
    plumber_log.info("=== run start: %d phases ===", len(steps))
    result = build_strategy(config).execute(input_pair, steps, output_pair, run_params)
    plumber_log.info("=== run end ===")
    return result
