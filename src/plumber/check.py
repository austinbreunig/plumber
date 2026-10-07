"""`plumber check`: cheap checks that run no phase code, plus the preflight inside `run`.

Layers, cheapest first:
  structural  config only, nothing imported
  static      import + inspect.signature, no phase code runs
  runtime     probe.py runs the phases on `check.sample` (only from `plumber check`, not `run`)

Every check is a plain function `fn(config, overrides) -> list[Finding]`. To add a check,
write one and append it to STRUCTURAL_CHECKS or STATIC_CHECKS.
"""

import inspect
import json
from typing import NamedTuple

from plumber.entries import name_of, params_of
from plumber.probe import probe
from plumber.resolver import resolve

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"

# Which `partition:` keys each execution strategy understands. A key a strategy does not list
# is a FAIL. The multiprocess ticket adds its row here, e.g.
#   "local-multiprocess": {"worker_count", "chunk_size", "by"}
STRATEGY_PARTITION_KEYS = {
    "local-sequential": set(),
}
DEFAULT_STRATEGY = "local-sequential"


class Finding(NamedTuple):
    """One problem. `label` is the report row it belongs to ("input", "P1", "partition", ...)."""

    label: str
    status: str
    message: str


def phase_labels(config):
    return [f"P{number}" for number in range(1, len(config.get("phases") or []) + 1)]


# ---- structural layer -------------------------------------------------------------------


def check_phase_fields(config, overrides):
    findings = []
    for label, entry in zip(phase_labels(config), config.get("phases") or []):
        if "path" not in entry:
            findings.append(Finding(label, FAIL, "missing `path`"))
        if "partitionable" not in entry:
            findings.append(Finding(label, FAIL, "missing `partitionable` (true or false)"))
        elif not isinstance(entry["partitionable"], bool):
            findings.append(Finding(label, FAIL, "`partitionable` must be true or false"))
        if not isinstance(entry.get("checkpoint", False), bool):
            findings.append(Finding(label, FAIL, "`checkpoint` must be true or false"))
    return findings


def check_checkpoints_block(config, overrides):
    block = config.get("checkpoints")
    if block is None:
        return []
    if not isinstance(block, dict):
        return [Finding("checkpoints", FAIL, "`checkpoints` must be a mapping with a `dir`")]
    if not isinstance(block.get("dir"), str):
        return [Finding("checkpoints", FAIL, "`checkpoints.dir` must be a path string")]
    return []


def check_partition_suits_strategy(config, overrides):
    """The partition spec may only use keys the chosen strategy understands."""
    strategy = config.get("strategy", DEFAULT_STRATEGY)
    if strategy not in STRATEGY_PARTITION_KEYS:
        known = ", ".join(sorted(STRATEGY_PARTITION_KEYS))
        return [Finding("strategy", FAIL, f"unknown strategy {strategy!r} (known: {known})")]
    allowed = STRATEGY_PARTITION_KEYS[strategy]
    return [
        Finding("partition", FAIL, f"key {key!r} is not used by strategy {strategy!r}")
        for key in (config.get("partition") or {})
        if key not in allowed
    ]


STRUCTURAL_CHECKS = [check_phase_fields, check_checkpoints_block, check_partition_suits_strategy]


# ---- static layer -----------------------------------------------------------------------


def entries_to_check(config):
    """(label, entry, takes_data) for input, every phase, and output (if there is one)."""
    entries = []
    if config.get("input"):
        entries.append(("input", config["input"], False))
    for label, entry in zip(phase_labels(config), config.get("phases") or []):
        entries.append((label, entry, True))
    if config.get("output"):
        entries.append(("output", config["output"], True))
    return entries


def check_signature(label, fn, params, takes_data):
    """Compare the configured params with the function's signature."""
    parameters = list(inspect.signature(fn).parameters.values())
    if takes_data:
        parameters = parameters[1:]  # the first argument is the data
    accepts_any = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters)
    named = [p for p in parameters if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]
    names = [p.name for p in named]
    shown = ", ".join(str(p) for p in parameters)

    findings = []
    for key in params:
        if key not in names and not accepts_any:
            findings.append(Finding(label, FAIL, f"unexpected param {key!r} (signature: {shown})"))
    for p in named:
        if p.default is p.empty and p.name not in params:
            findings.append(Finding(label, FAIL, f"missing required param {p.name!r}"))
    return findings


def check_paths_and_signatures(config, overrides):
    findings = []
    for label, entry, takes_data in entries_to_check(config):
        if "path" not in entry:
            continue  # the structural layer already reported it
        try:
            fn = resolve(entry["path"])
        except Exception as error:  # importing runs user code, which can raise anything
            findings.append(Finding(label, FAIL, f"cannot resolve {entry['path']!r}: {error}"))
            continue
        if callable(fn):
            findings += check_signature(label, fn, params_of(entry), takes_data)
        else:
            findings.append(Finding(label, FAIL, f"{entry['path']!r} is not callable"))
    return findings


def check_unknown_overrides(config, overrides):
    """A --params key that no phase lists is probably a typo."""
    listed = {key for entry in config.get("phases") or [] for key in params_of(entry)}
    return [
        Finding("--params", WARN, f"{key!r}: no phase lists this param, so it is ignored")
        for key in overrides
        if key not in listed
    ]


STATIC_CHECKS = [check_paths_and_signatures, check_unknown_overrides]


# ---- report -----------------------------------------------------------------------------


def row_for(label, findings, config):
    entries = {lab: entry for lab, entry, _ in entries_to_check(config)}
    mine = [f for f in findings if f.label == label]
    entry = entries.get(label)
    statuses = {f.status for f in mine}
    status = next((s for s in (FAIL, WARN, SKIP) if s in statuses), PASS)
    return {
        "label": label,
        "name": name_of(entry) if entry and "path" in entry else None,
        "status": status,
        "messages": [f.message for f in mine],
    }


def run_probe(config, overrides, findings):
    """The runtime layer. Returns (findings, note for the report's `runtime_probe` line)."""
    sample = (config.get("check") or {}).get("sample")
    if not sample:
        return [], "not run (no check.sample)"
    if any(f.status == FAIL for f in findings):
        return [], "not run (fix the FAIL rows first)"
    return [Finding(*t) for t in probe(sample, config["phases"], overrides)], f"ran on {sample}"


def check(config, overrides=None, runtime=True):
    """Run the structural, static and (if `runtime` and `check.sample` is set) runtime layers.

    Returns the report as a plain dict. `run`'s preflight passes runtime=False.
    """
    overrides = overrides or {}
    findings = []
    for check_fn in STRUCTURAL_CHECKS + STATIC_CHECKS:
        findings += check_fn(config, overrides)
    probe_note = "not run (no check.sample)"
    if runtime:
        probe_findings, probe_note = run_probe(config, overrides, findings)
        findings += probe_findings

    labels = [label for label, _, _ in entries_to_check(config)]
    labels += [f.label for f in findings if f.label not in labels]  # config-level rows, once
    labels = list(dict.fromkeys(labels))
    rows = [row_for(label, findings, config) for label in labels]
    return {
        "ok": all(row["status"] != FAIL for row in rows),
        "rows": rows,
        "runtime_probe": probe_note,
    }


def format_report(report):
    lines = []
    for row in report["rows"]:
        name = row["name"] or ""
        line = f"{row['label']:<10} {name:<28} {row['status']}"
        if row["messages"]:
            line += "   " + "; ".join(row["messages"])
        lines.append(line.rstrip())
    lines.append(f"runtime probe: {report['runtime_probe']}")
    return "\n".join(lines)


def write_report(report, path="report.json"):
    with open(path, "w") as file:
        json.dump(report, file, indent=2)


def preflight(config):
    """Run before `run`. Any FAIL stops the run; a WARN never does."""
    report = check(config, runtime=False)
    if not report["ok"]:
        raise SystemExit("plumber check failed, nothing was run:\n" + format_report(report))
