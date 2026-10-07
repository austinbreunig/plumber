"""The shapes every part of plumber agrees on: phases, steps, results, strategies."""

from dataclasses import dataclass
from typing import Any, Callable, Generic, Optional, Protocol, TypeVar

Payload = TypeVar("Payload")


class PhaseModule(Protocol[Payload]):
    """A resolved phase: a plain function `run(data, **params) -> data`."""

    def __call__(self, data: Payload, **params: Any) -> Payload: ...


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


class ExecutionStrategy(Protocol[Payload]):
    def execute(
        self,
        input: Bound,
        steps: list[Step],
        output: Optional[Bound],
        run_params: dict[str, Any],
    ) -> Result[Payload]: ...
