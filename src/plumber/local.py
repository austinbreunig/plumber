"""LocalSequential: run everything in this process, one phase after another."""

from plumber.checkpoint import write_checkpoint
from plumber.protocols import Result, load, run_phase, save, with_user_level


class LocalSequential:
    @with_user_level
    def execute(self, input, steps, output, run_params):
        data = load(input)
        for step in steps:
            data = run_phase(step, data)
            if step.checkpoint:
                write_checkpoint(data, run_params["checkpoint_dir"], step.name)
        save(output, data)
        return Result(data)
