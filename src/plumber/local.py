"""LocalSequential: run everything in this process, one phase after another."""

from plumber.protocols import Result


class LocalSequential:
    def execute(self, input, steps, output, run_params):
        input_fn, input_params = input
        data = input_fn(**input_params)
        for step in steps:
            data = step.fn(data, **step.params)
        if output is not None:
            output_fn, output_params = output
            output_fn(data, **output_params)
        return Result(data)
