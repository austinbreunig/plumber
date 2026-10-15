"""LocalSequential: run everything in this process, one phase after another."""

from plumber.protocols import Result, load, run_phase, save, with_user_level


class LocalSequential:
    @with_user_level
    def execute(self, input, steps, output, run_params):
        data = load(input)
        for step in steps:
            data = run_phase(step, data, run_params)
        save(output, data)
        return Result(data)
