"""Write `plumber.draft.yaml` in the repo root.

Run with any Python; the full config text comes on stdin:
  python write_draft.py [repo] < config.yaml
Prints {"draft": "<path>", "base": "<hash or none>"}.
Line 1 is `# base: <hash of plumber.yaml>` (`none` when there is no plumber.yaml).
The whole file is rewritten each time, so a crash loses nothing already written.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from base_hash import hash_file, split_base  # noqa: E402

DRAFT = "plumber.draft.yaml"
CONFIG = "plumber.yaml"


def write_draft(repo, yaml_text):
    repo = Path(repo)
    base = hash_file(repo / CONFIG)
    body = split_base(yaml_text)[1]  # never stack `# base:` lines
    draft = repo / DRAFT
    temp = repo / (DRAFT + ".tmp")
    temp.write_text(f"# base: {base}\n{body}", encoding="utf-8")
    temp.replace(draft)  # swap in one step so a kill never leaves half a file
    return draft


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    draft = write_draft(repo, sys.stdin.read())
    print(json.dumps({"draft": str(draft), "base": hash_file(Path(repo) / CONFIG)}))


if __name__ == "__main__":
    main()
