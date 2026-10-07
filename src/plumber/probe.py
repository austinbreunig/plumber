"""The runtime probe: run the phases on a small sample file and report what went wrong.

Only `plumber check` calls this. It runs user code on real data, so `run`'s preflight skips it.
It returns `Finding`s, like the other layers.
"""

import geopandas as gpd

from plumber.entries import FAIL, SKIP, WARN, Finding, params_of, phase_label
from plumber.resolver import resolve


def probe_phase(fn, params, partitionable, data):
    """Call one phase. Returns (output, [(status, message), ...]). Output is None on a crash."""
    try:
        output = fn(data.copy(), **params)
    except Exception as error:  # user code can raise anything
        return None, [(FAIL, f"{type(error).__name__}: {error}")]

    results = []
    if partitionable and not output.equals(fn(data.copy(), **params)):
        results.append((FAIL, "different output on identical input (shared state?)"))
    if getattr(output, "crs", None) != getattr(data, "crs", None):
        results.append((WARN, f"CRS changed from {data.crs} to {output.crs}"))
    dropped = [column for column in data.columns if column not in output.columns]
    if dropped:
        results.append((WARN, f"columns dropped: {', '.join(map(str, dropped))}"))
    return output, results


def probe(sample, phases, overrides):
    """Chain the sample through `phases` (config entries) in order.

    After a crash every later phase is SKIP.
    """
    try:
        data = gpd.read_parquet(sample)
    except Exception as error:
        return [Finding("check.sample", FAIL, f"cannot read {sample!r}: {error}")]

    findings = []
    crashed = False
    for number, entry in enumerate(phases, start=1):
        label = phase_label(number)
        if crashed:
            findings.append(Finding(label, SKIP, "upstream phase failed"))
            continue
        params = {key: overrides.get(key, value) for key, value in params_of(entry).items()}
        output, results = probe_phase(
            resolve(entry["path"]), params, entry["partitionable"], data
        )
        findings += [Finding(label, status, message) for status, message in results]
        if output is None:
            crashed = True
        else:
            data = output
    return findings
