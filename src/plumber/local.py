"""LocalSequential: run everything in this process, one phase after another."""

from plumber.checkpoint import write_checkpoint
from plumber.protocols import Result, load, save


class LocalSequential:
    def execute(self, input, steps, output, run_params):
        data = load(input)
        for step in steps:
            data = step.fn(data, **step.params)
            if step.checkpoint:
                write_checkpoint(data, run_params["checkpoint_dir"], step.name)
        save(output, data)
        return Result(data)
