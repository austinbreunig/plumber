"""The runtime probe: run the phases on a small sample file and report what went wrong.

Only `plumber check` calls this. It runs user code on real data, so `run`'s preflight skips it.
Findings are `(label, status, message)` tuples; `check.py` turns them into `Finding`s.
"""

import geopandas as gpd

from plumber.entries import params_of
from plumber.resolver import resolve


def same_output(first, second):
    return first.equals(second)


def probe_phase(fn, params, partitionable, data):
    """Call one phase. Returns (output, [(status, message), ...]). Output is None on a crash."""
    try:
        output = fn(data.copy(), **params)
    except Exception as error:  # user code can raise anything
        return None, [("FAIL", f"{type(error).__name__}: {error}")]

    results = []
    if partitionable and not same_output(output, fn(data.copy(), **params)):
        results.append(("FAIL", "different output on identical input (shared state?)"))
    if getattr(output, "crs", None) != getattr(data, "crs", None):
        results.append(("WARN", f"CRS changed from {data.crs} to {output.crs}"))
    dropped = [column for column in data.columns if column not in output.columns]
    if dropped:
        results.append(("WARN", f"columns dropped: {', '.join(map(str, dropped))}"))
    return output, results


def probe(sample, phases, overrides):
    """Chain the sample through `phases` (config entries) in order.

    After a crash every later phase is SKIP.
    """
    try:
        data = gpd.read_parquet(sample)
    except Exception as error:
        return [("check.sample", "FAIL", f"cannot read {sample!r}: {error}")]

    findings = []
    crashed = False
    for number, entry in enumerate(phases, start=1):
        label = f"P{number}"
        if crashed:
            findings.append((label, "SKIP", "upstream phase failed"))
            continue
        params = {key: overrides.get(key, value) for key, value in params_of(entry).items()}
        output, results = probe_phase(
            resolve(entry["path"]), params, entry["partitionable"], data
        )
        findings += [(label, status, message) for status, message in results]
        if output is None:
            crashed = True
        else:
            data = output
    return findings
