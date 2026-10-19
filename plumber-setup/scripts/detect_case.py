"""Detect which starting case the setup skill is in.

Run with the target repo's venv Python and the repo as the working directory:
  <venv>/bin/python detect_case.py [repo]
Prints JSON: {"case": "resume"|"A"|"B"|"C", "findings": [...], "draft_error": null|"...",
"drift": bool}
`drift` is true when the draft's `# base:` no longer matches plumber.yaml (resume only).

Order, first match wins:
  1. a draft exists            -> resume
  2. no plumber.yaml           -> A (fresh)
  3. check has FAIL or WARN    -> C (fix); a config that will not load counts as a FAIL
  4. otherwise                 -> B (change)
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from base_hash import hash_file, read_base  # noqa: E402

from plumber import check, load_config  # noqa: E402

CONFIG = "plumber.yaml"
DRAFT = "plumber.draft.yaml"


def load_error(path):
    """Why the config at `path` cannot be used, or None if it loads."""
    try:
        config = load_config(path)
    except Exception as error:  # a bad file can fail in many ways; report it in words
        return str(error)
    if not isinstance(config, dict):
        return "the top level must be a mapping"
    return None


def check_findings(path):
    """FAIL and WARN lines from `check` for the config at `path`. Broken config is one FAIL."""
    error = load_error(path)
    if error:
        return [f"config does not load: {error}"]
    report = check(load_config(path))
    return [
        f"{row['label']} {row['status']}: {'; '.join(row['messages'])}"
        for row in report["rows"]
        if row["status"] in ("FAIL", "WARN")
    ]


def has_drifted(repo):
    """True if plumber.yaml changed since the draft started (or the draft has no base line)."""
    base = read_base((Path(repo) / DRAFT).read_text(encoding="utf-8"))
    return base != hash_file(Path(repo) / CONFIG)


def detect_case(repo="."):
    repo = Path(repo)
    draft, config = repo / DRAFT, repo / CONFIG
    if draft.exists():
        return {
            "case": "resume",
            "findings": [],
            "draft_error": load_error(draft),
            "drift": has_drifted(repo),
        }
    if not config.exists():
        return {"case": "A", "findings": [], "draft_error": None, "drift": False}
    findings = check_findings(config)
    case = "C" if findings else "B"
    return {"case": case, "findings": findings, "draft_error": None, "drift": False}


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    os.chdir(repo)  # plumber resolves phase paths from the working directory
    print(json.dumps(detect_case(".")))


if __name__ == "__main__":
    main()
