"""Check the draft for interview mistakes `check` does not word well. Run before approval.

Run with any Python (reads the file as plain YAML):
  python lint_draft.py [draft]     (default: plumber.draft.yaml)
Prints {"problems": [...], "warnings": [...]}.
  problems: fix before approval (duplicate phase names, wrong `localmp` partition keys)
  warnings: tell the user (`localmp` with no partitionable phase, no output function)
"""

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from common import DRAFT  # noqa: E402

PARTITION_KEYS = ("by", "chunk_size", "worker_count")


def phase_name(entry):
    return entry.get("name", entry.get("path"))


def duplicate_names(phases):
    """One problem line per repeated phase name, e.g. 'a:run is used by phases 1 and 3'."""
    seen, problems = {}, []
    for number, entry in enumerate(phases, start=1):
        name = phase_name(entry)
        if name is None:
            continue
        seen.setdefault(name, []).append(number)
    for name, numbers in seen.items():
        if len(numbers) > 1:
            used = " and ".join(str(n) for n in numbers)
            problems.append(f"{name} is used by phases {used}: give each its own `name:`")
    return problems


def lint_config(config):
    phases = [p for p in config.get("phases") or [] if isinstance(p, dict)]
    problems = duplicate_names(phases)
    warnings = []
    execution = config.get("execution") or {}
    if execution.get("strategy") == "localmp":
        partition = execution.get("partition") or {}
        if sum(key in partition for key in PARTITION_KEYS) != 1 or len(partition) != 1:
            problems.append("localmp needs exactly one of: by, chunk_size, worker_count")
        if not any(p.get("partitionable") is True for p in phases):
            warnings.append(
                "localmp will not help: no phase is partitionable, so every phase runs whole"
            )
    if not config.get("output"):
        warnings.append("No `output:` in config: result discarded")
    return {"problems": problems, "warnings": warnings}


def lint_draft(path):
    with open(path, encoding="utf-8") as file:
        return lint_config(yaml.safe_load(file) or {})


def main():
    print(json.dumps(lint_draft(sys.argv[1] if len(sys.argv) > 1 else DRAFT)))


if __name__ == "__main__":
    main()
