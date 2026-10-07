"""LocalMultiprocess (`localmp`): run partitionable phases on pieces, in worker processes.

Flow: input -> split -> phases on pieces -> gather -> (non-partitionable phase) -> split again
-> ... -> gather -> output. `split` and `gather` are the two seams. Anything that needs the
whole dataset (a non-partitionable phase, the output function, later checkpoints) goes
through `gather`.
"""

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from plumber.protocols import Result

ROW = "_plumber_row"  # input row number, carried through the phases to restore order


def tag_rows(data):
    """Add the order column: each row's position in the input."""
    return data.assign(**{ROW: range(len(data))})


def split(data, partition):
    """Cut `data` into pieces by one of: `by` (columns), `chunk_size`, `worker_count`."""
    if "by" in partition:
        return [piece for _, piece in data.groupby(partition["by"], sort=True)]
    if "chunk_size" in partition:
        size = partition["chunk_size"]
        return [data.iloc[start : start + size] for start in range(0, len(data), size)]
    positions = np.array_split(np.arange(len(data)), partition["worker_count"])
    return [data.iloc[p] for p in positions if len(p)]


def join(pieces):
    """Join pieces into one table in the input's row order. Keeps the order column."""
    return pd.concat(pieces).sort_values(ROW, kind="stable")


def gather(pieces):
    """`join`, then drop the order column: the data as the user's own functions see it."""
    return join(pieces).drop(columns=ROW)


class LocalMultiprocess:
    def __init__(self, partition):
        self.partition = partition

    def execute(self, input, steps, output, run_params):
        input_fn, input_params = input
        data = input_fn(**input_params)
        data = tag_rows(data)
        workers = self.partition.get("worker_count")
        pieces = None  # set while the data is split; None means `data` holds everything
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for step in steps:
                if step.partitionable:
                    pieces = split(data, self.partition) if pieces is None else pieces
                    futures = [pool.submit(step.fn, piece, **step.params) for piece in pieces]
                    pieces = [future.result() for future in futures]
                else:
                    if pieces is not None:
                        data, pieces = join(pieces), None
                    data = step.fn(data, **step.params)
        data = gather(pieces) if pieces is not None else data.drop(columns=ROW)
        if output is not None:
            output_fn, output_params = output
            output_fn(data, **output_params)
        return Result(data)
