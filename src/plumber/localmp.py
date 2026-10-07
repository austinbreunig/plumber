"""LocalMultiprocess (`localmp`): run partitionable phases on pieces, in worker processes.

Flow: input -> split -> phases on pieces -> join -> (non-partitionable phase) -> split again
-> ... -> join -> output. `split` and `join` are the two seams. Anything that needs the
whole dataset (a non-partitionable phase, the output function, later checkpoints) goes
through `join`.
"""

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from plumber.checkpoint import checkpoint_dir, write_checkpoint
from plumber.protocols import Result


def split(data, partition):
    """Cut `data` into pieces by one of: `by` (columns), `chunk_size`, `worker_count`."""
    if "by" in partition:
        return [piece for _, piece in data.groupby(partition["by"], sort=True, dropna=False)]
    if "chunk_size" in partition:
        size = partition["chunk_size"]
        return [data.iloc[start : start + size] for start in range(0, len(data), size)]
    positions = np.array_split(np.arange(len(data)), partition["worker_count"])
    return [data.iloc[p] for p in positions if len(p)]


def join(pieces, order):
    """Join pieces into one table in `order`, the index the data had before it was split.

    Rows sort by where their index label sat in `order`. A phase must keep the index
    (and it must be unique) for this to restore the input order.
    """
    joined = pd.concat(pieces)
    return joined.iloc[np.argsort(order.get_indexer(joined.index), kind="stable")]


def whole(data, pieces, order):
    """All the data in input order: `data` if not split, else the joined pieces."""
    return data if pieces is None else join(pieces, order)


class LocalMultiprocess:
    def __init__(self, partition):
        self.partition = partition

    def execute(self, input, steps, output, run_params):
        input_fn, input_params = input
        data = input_fn(**input_params)
        workers = self.partition.get("worker_count")
        pieces = None  # set while the data is split; None means `data` holds everything
        order = None  # the index of `data` when it was split
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for step in steps:
                if step.partitionable:
                    if pieces is None:
                        order = data.index
                        pieces = split(data, self.partition)
                    futures = [pool.submit(step.fn, piece, **step.params) for piece in pieces]
                    pieces = [future.result() for future in futures]
                else:
                    data, pieces = whole(data, pieces, order), None
                    data = step.fn(data, **step.params)
                if step.checkpoint:
                    # Gather point: whole data in input order, write one file, split again.
                    data, pieces = whole(data, pieces, order), None
                    write_checkpoint(data, checkpoint_dir(run_params), step.name)
        data = whole(data, pieces, order)
        if output is not None:
            output_fn, output_params = output
            output_fn(data, **output_params)
        return Result(data)
