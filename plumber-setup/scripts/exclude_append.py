"""Append lines to the repo's `.git/info/exclude` (never `.gitignore`).

Run with any Python: `python exclude_append.py <repo> <line>...`. Prints JSON:
  {"status": "ok", "file": "...", "added": [...], "skipped": [...]}
  {"status": "skipped", "reason": "not a git repo"}
Append only. Lines already in the file are skipped.
"""

import json
import subprocess
import sys
from pathlib import Path


def exclude_file(repo):
    """Path of the git exclude file for `repo`, or None outside a git repo."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--git-path", "info/exclude"],
            cwd=repo, capture_output=True, text=True, timeout=30,
        )
    except OSError:
        return None
    if done.returncode != 0:
        return None
    return (Path(repo) / done.stdout.strip()).resolve()


def exclude_append(repo, lines):
    path = exclude_file(repo)
    if path is None:
        return {"status": "skipped", "reason": "not a git repo"}
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    have = {line.strip() for line in text.splitlines()}
    added, skipped = [], []
    for line in lines:
        if line in have:
            skipped.append(line)
        else:
            added.append(line)
            have.add(line)
    if added:
        if text and not text.endswith("\n"):
            text += "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "".join(f"{line}\n" for line in added), encoding="utf-8")
    return {"status": "ok", "file": str(path), "added": added, "skipped": skipped}


def main():
    print(json.dumps(exclude_append(sys.argv[1], sys.argv[2:])))


if __name__ == "__main__":
    main()
