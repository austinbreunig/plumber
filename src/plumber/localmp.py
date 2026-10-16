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
from queue import Empty

import numpy as np
import pandas as pd

from plumber.protocols import (
    Result,
    load,
    plumber_log,
    run_phase,
    save,
    section,
    tag_records,
    write_step_checkpoint,
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
    plumber_log.setLevel(logging.DEBUG)  # as `user_level` does here; spawn starts unset


def run_piece(step, piece):
    """Run a phase on one piece in a worker, then mark the end of its log lines.

    The mark is the phase name, so a late mark from an earlier phase is never miscounted.
    """
    try:
        with tag_records(step.name):
            return step.fn(piece, **step.params)
    finally:
        _worker_queue.put(step.name)


def pump(queue, phase, timeout):
    """Take one item off the queue and emit it here.

    Returns 1 for `phase`'s end mark, 0 for anything else, None if nothing came in `timeout`.
    """
    try:
        item = queue.get(timeout=timeout)
    except Empty:
        return None
    if isinstance(item, str):  # an end mark
        return int(item == phase)
    logging.getLogger(item.name).handle(item)
    return 0


def collect(futures, queue, phase, timeout=5):
    """The pieces' results, with their log lines emitted here as they arrive.

    Even if a piece raised: stop pieces not started, let the running ones finish, then show
    every line they made before the phase ends. A piece that died (killed worker, task that
    would not pickle) never sends its end mark, so give up after `timeout` seconds of silence.
    """
    marks = 0
    try:
        while not all(f.done() for f in futures) and not any(failed(f) for f in futures):
            marks += pump(queue, phase, 0.1) or 0
        return [future.result() for future in futures]
    finally:
        for future in futures:
            future.cancel()
        wait(futures)
        wanted = sum(not future.cancelled() for future in futures)
        while marks < wanted:
            seen = pump(queue, phase, timeout)
            if seen is None:
                plumber_log.warning("a worker sent no end mark; its log lines may be missing")
                break
            marks += seen


def failed(future):
    return future.done() and not future.cancelled() and future.exception() is not None


class LocalMultiprocess:
    def __init__(self, partition):
        self.partition = partition

    def execute(self, input, steps, output, run_params):
        data = load(input)
        workers = self.partition.get("worker_count")
        pieces = None  # set while the data is split; None means `data` holds everything
        order = None  # the index of `data` when it was split
        queue = multiprocessing.Queue()
        level = logging.getLogger().getEffectiveLevel()
        try:
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
                            pieces = collect(futures, queue, step.name)
                            if step.checkpoint:
                                # Gather point: whole data in input order, write one file,
                                # split again.
                                data, pieces = whole(data, pieces, order), None
                                write_step_checkpoint(step, data, run_params)
                    else:
                        data, pieces = whole(data, pieces, order), None
                        data = run_phase(step, data, run_params)
        finally:
            queue.close()
        data = whole(data, pieces, order)
        save(output, data)
        return Result(data)
