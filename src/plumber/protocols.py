"""The shapes every part of plumber agrees on: phases, steps, results, strategies."""

from dataclasses import dataclass
from typing import Any, Callable, Generic, Optional, Protocol, TypeVar

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


def load(input: Bound):
    """Call the user's input function."""
    fn, params = input
    return fn(**params)


def save(output: Optional[Bound], data) -> None:
    """Call the user's output function, if there is one."""
    if output is not None:
        fn, params = output
        fn(data, **params)


class ExecutionStrategy(Protocol[Payload]):
    def execute(
        self,
        input: Bound,
        steps: list[Step],
        output: Optional[Bound],
        run_params: dict[str, Any],
    ) -> Result[Payload]: ...
