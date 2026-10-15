"""The shapes every part of plumber agrees on: phases, steps, results, strategies."""

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
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
    before = root.level, plumber_log.level
    root.setLevel(parse_user_level(run_params.get("user_level", DEFAULT_USER_LEVEL)))
    plumber_log.setLevel(logging.INFO)
    try:
        yield
    finally:
        root.setLevel(before[0])
        plumber_log.setLevel(before[1])


def phase_heading(name):
    """Open a section of the Run log: `=== phase <name> ===`.

    Input and output functions get one too, as `=== input ===` / `=== output ===`.
    """
    plumber_log.info("=== %s ===", name if name in ("input", "output") else f"phase {name}")


def phase_closing(name, ok):
    """Close a section: `=== end <name>: ok ===`, or `failed` if the phase raised."""
    plumber_log.info("=== end %s: %s ===", name, "ok" if ok else "failed")


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
            record.msg = f"[{name}|{record.processName}] {record.getMessage()}"
            record.args = ()
        return record

    logging.setLogRecordFactory(tagged)
    try:
        yield
    finally:
        logging.setLogRecordFactory(make_record)


@contextmanager
def section(name):
    """The shared phase wrapper: heading, tagged User log, closing line (even on a crash)."""
    phase_heading(name)
    ok = False
    try:
        with tag_records(name):
            yield
        ok = True
    finally:
        phase_closing(name, ok)


def with_user_level(execute):
    """Decorator for a strategy's `execute`: run it inside `user_level(run_params)`."""

    @wraps(execute)
    def wrapper(self, input, steps, output, run_params):
        with user_level(run_params):
            return execute(self, input, steps, output, run_params)

    return wrapper


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
    """Call the user's input function."""
    fn, params = input
    with section("input"):
        return fn(**params)


def save(output: Optional[Bound], data) -> None:
    """Call the user's output function, if there is one."""
    if output is not None:
        fn, params = output
        with section("output"):
            fn(data, **params)


class ExecutionStrategy(Protocol[Payload]):
    """Runs the input, the steps, then the output.

    The signature is the whole interface. These logging rules are part of the contract
    (see ADR 0001):

    - Wrap every user call with `section` (or `run_phase`, `load`, `save`) so the Run log
      has a heading, tagged User log lines, and a closing line per phase.
    - Line format, fixed in v1 (`<name>` is the step name, `<process>` the process name):
        `=== run start: <n> phases ===` / `=== run end ===`   (written by `run`)
        `=== input ===` / `=== phase <name> ===` / `=== output ===`
        `[<name>|<process>] <user message>`
        `=== end <name>: ok ===` or `=== end <name>: failed ===`
    - Decorate `execute` with `@with_user_level` so `user_level` filters
      the User log (and never the Plumber log).
    - Ordering: every line of phase N is delivered before the heading of phase N+1.
      How lines travel back to the main process is the strategy's own job.
    """

    def execute(
        self,
        input: Bound,
        steps: list[Step],
        output: Optional[Bound],
        run_params: dict[str, Any],
    ) -> Result[Payload]: ...
