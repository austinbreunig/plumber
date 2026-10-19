"""Write `plumber.draft.yaml` in the repo root.

Run with any Python; the full config text comes on stdin:
  python write_draft.py [repo] [--rebase] < config.yaml
Prints {"draft": "<path>", "base": "<hash or none>"}.
Line 1 is `# base: <hash of plumber.yaml>` (`none` when there is no plumber.yaml). It is set when
the draft is created and kept on every rewrite. `--rebase` re-stamps it from the current
plumber.yaml (the "overwrite" choice after drift).
The whole file is rewritten each time, so a crash loses nothing already written.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from base_hash import hash_file, read_base, split_base  # noqa: E402
from common import CONFIG, DRAFT  # noqa: E402


def draft_base(repo, rebase=False):
    """The base hash for the draft: the existing draft's, else from plumber.yaml."""
    draft = repo / DRAFT
    if draft.exists() and not rebase:
        old = read_base(draft.read_text(encoding="utf-8"))
        if old is not None:
            return old
    return hash_file(repo / CONFIG)


def write_draft(repo, yaml_text, rebase=False):
    repo = Path(repo)
    base = draft_base(repo, rebase)
    body = split_base(yaml_text)[1]  # never stack `# base:` lines
    draft = repo / DRAFT
    temp = repo / (DRAFT + ".tmp")
    temp.write_text(f"# base: {base}\n{body}", encoding="utf-8")
    temp.replace(draft)  # swap in one step so a kill never leaves half a file
    return draft


def main():
    repo = next((a for a in sys.argv[1:] if a != "--rebase"), None) or "."
    draft = write_draft(repo, sys.stdin.read(), rebase="--rebase" in sys.argv)
    print(json.dumps({"draft": str(draft), "base": read_base(draft.read_text(encoding="utf-8"))}))


if __name__ == "__main__":
    main()
