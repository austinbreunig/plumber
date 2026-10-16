"""The shapes every part of plumber agrees on: phases, steps, results, strategies."""

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Generic, Optional, Protocol, TypeVar

from plumber.checkpoint import write_checkpoint

Payload = TypeVar("Payload")


@dataclass(frozen=True)
class Step:
    """One configured phase, ready to run."""

    name: str
    fn: Callable
    params: dict
    partitionable: bool
    checkpoint: bool


class Result(Generic[Payload]):
    """What a strategy hands back. Only `.collect()` is public."""

    def __init__(self, data: Payload):
        self._data = data

    def collect(self) -> Payload:
        return self._data


# A pre-bound (function, params) pair. The strategy calls `fn(**params)` (input)
# or `fn(data, **params)` (output).
Bound = tuple[Callable, dict[str, Any]]


plumber_log = logging.getLogger("plumber")

DEFAULT_USER_LEVEL = "INFO"
LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
OFF = logging.CRITICAL + 1


def parse_user_level(name):
    """Turn a level name (any case) or `off` into a logging level number.

    Raises ValueError for anything else.
    """
    if name is False:  # YAML reads an unquoted `off` as False
        return OFF
    upper = str(name).upper()
    if upper == "OFF":
        return OFF
    if upper not in LEVELS:
        raise ValueError(f"{name!r} is not a level (use {', '.join(LEVELS)} or off)")
    return getattr(logging, upper)


@contextmanager
def user_level(run_params):
    """Filter the User log to `run_params["user_level"]` (default INFO) while inside.

    The root logger gets the level, so every logger without a level of its own (user code,
    library loggers) follows it. The `plumber` logger has its own level, so it always shows.
    """
    root = logging.getLogger()
    root_before, plumber_before = root.level, plumber_log.level
    root.setLevel(parse_user_level(run_params.get("user_level", DEFAULT_USER_LEVEL)))
    plumber_log.setLevel(logging.DEBUG)
    try:
        yield
    finally:
        root.setLevel(root_before)
        plumber_log.setLevel(plumber_before)


@contextmanager
def tag_records(name):
    """Prefix every User log record made inside with `[<name>|<process>] `.

    Plumber's own loggers (`plumber`, `plumber.*`) are left alone. A worker process
    can use this on its own to tag the records it makes.
    """
    make_record = logging.getLogRecordFactory()

    def tagged(*args, **kwargs):
        record = make_record(*args, **kwargs)
        if record.name != "plumber" and not record.name.startswith("plumber."):
            # Keep msg and args apart: a bad logging call then fails where logging
            # always handles it (the handler), not inside the user's phase.
            tag = f"[{name}|{record.processName}] ".replace("%", "%%")
            record.msg = tag + str(record.msg)
        return record

    logging.setLogRecordFactory(tagged)
    try:
        yield
    finally:
        logging.setLogRecordFactory(make_record)


@contextmanager
def section(name, label=None):
    """The shared phase wrapper: heading, tagged User log, closing line (even on a crash).

    `label` is the heading text; it defaults to `phase <name>`. A crash is logged on the
    Plumber log, with its traceback, before the closing line.
    """
    plumber_log.info("=== %s ===", label or f"phase {name}")
    ok = False
    try:
        with tag_records(name):
            yield
        ok = True
    except Exception as error:
        plumber_log.exception("phase %s failed: %r", name, error)
        raise
    finally:
        plumber_log.info("=== end %s: %s ===", name, "ok" if ok else "failed")


def run_phase(step, data, run_params):
    """Call one phase as `fn(data, **params)` inside its section.

    If the step opts in, its checkpoint is saved inside the section too, so the
    "checkpoint saved" line sits under that phase's heading.
    """
    with section(step.name):
        data = step.fn(data, **step.params)
        if step.checkpoint:
            write_checkpoint(data, run_params["checkpoint_dir"], step.name)
        return data


def load(input: Bound):
    """Call the user's input function. One of plumber's own (a `--from` read) gets no section."""
    fn, params = input
    if fn.__module__.startswith("plumber."):
        return fn(**params)
    with section("input", "input"):
        return fn(**params)


def save(output: Optional[Bound], data) -> None:
    """Call the user's output function, if there is one."""
    if output is not None:
        fn, params = output
        with section("output", "output"):
            fn(data, **params)


class ExecutionStrategy(Protocol[Payload]):
    """Runs the input, the steps, then the output.

    The signature is the whole interface. The logging rules are part of the contract: see
    ADR 0001 (wrap every user call with `section`, `run_phase`, `load` or `save`; deliver
    every line of phase N before the heading of phase N+1). `run` applies `user_level`.
    """

    def execute(
        self,
        input: Bound,
        steps: list[Step],
        output: Optional[Bound],
        run_params: dict[str, Any],
    ) -> Result[Payload]: ...
