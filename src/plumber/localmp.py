"""LocalMultiprocess (`localmp`): run partitionable phases on pieces, in worker processes.

Flow: input -> split -> phases on pieces -> join -> (non-partitionable phase) -> split again
-> ... -> join -> output. `split` and `join` are the two seams. Anything that needs the
whole dataset (a non-partitionable phase, the output function, later checkpoints) goes
through `join`.
"""

import logging
import logging.handlers
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, wait

import numpy as np
import pandas as pd

from plumber.checkpoint import write_checkpoint
from plumber.protocols import (
    Result,
    load,
    run_phase,
    save,
    section,
    tag_records,
    with_user_level,
)


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


_worker_queue = None  # set in each worker by `start_worker`; a queue can't travel with a task


def start_worker(queue, level):
    """Worker setup: the only Run log handler is one that sends records to `queue`.

    Dropping inherited handlers and tagger (fork) and setting the level by hand (spawn) makes both
    start methods behave the same.
    """
    global _worker_queue
    _worker_queue = queue
    logging.setLogRecordFactory(logging.LogRecord)  # fork copies the main process's tagger
    root = logging.getLogger()
    root.handlers[:] = [logging.handlers.QueueHandler(queue)]
    root.setLevel(level)


def run_piece(step, piece):
    """Run a phase on one piece in a worker, then mark the end of its log lines."""
    try:
        with tag_records(step.name):
            return step.fn(piece, **step.params)
    finally:
        _worker_queue.put(None)


def replay(queue, count):
    """Emit the workers' records here, until `count` pieces have said they are done."""
    while count:
        record = queue.get()
        if record is None:
            count -= 1
        else:
            logging.getLogger(record.name).handle(record)


class LocalMultiprocess:
    def __init__(self, partition):
        self.partition = partition

    @with_user_level
    def execute(self, input, steps, output, run_params):
        data = load(input)
        workers = self.partition.get("worker_count")
        pieces = None  # set while the data is split; None means `data` holds everything
        order = None  # the index of `data` when it was split
        queue = multiprocessing.Queue()
        level = logging.getLogger().getEffectiveLevel()
        with ProcessPoolExecutor(
            max_workers=workers, initializer=start_worker, initargs=(queue, level)
        ) as pool:
            for step in steps:
                if step.partitionable:
                    if pieces is None:
                        order = data.index
                        pieces = split(data, self.partition)
                    with section(step.name):
                        futures = [pool.submit(run_piece, step, piece) for piece in pieces]
                        try:
                            results = [future.result() for future in futures]
                        finally:
                            # Even if a piece raised: stop pieces not started, let the running
                            # ones finish, then show every line they made before the phase ends.
                            for future in futures:
                                future.cancel()
                            wait(futures)
                            replay(queue, sum(not future.cancelled() for future in futures))
                        pieces = results
                        if step.checkpoint:
                            # Gather point: whole data in input order, write one file, split again.
                            data, pieces = whole(data, pieces, order), None
                            write_checkpoint(data, run_params["checkpoint_dir"], step.name)
                else:
                    data, pieces = whole(data, pieces, order), None
                    data = run_phase(step, data, run_params)
        data = whole(data, pieces, order)
        save(output, data)
        return Result(data)
