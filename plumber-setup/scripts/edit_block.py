"""Replace one top-level YAML block in the draft, as text.

Run with the target repo's venv Python and the repo as the working directory:
  <venv>/bin/python edit_block.py <repo> <key> < new_block.yaml
The new block (starting with `<key>:`) comes on stdin. Prints JSON:
  {"draft": "<path>", "error": null | "<why the draft does not load>"}
Edits the draft if there is one, else starts one from `plumber.yaml`.
Only the lines of that block change. Comments, blank lines and key order elsewhere stay as is.
Other helpers can reuse `replace_block(text, key, new_block)`.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import CONFIG, DRAFT  # noqa: E402
from write_draft import write_draft  # noqa: E402


def block_range(lines, key):
    """(start, end) line indexes of the top-level `key` block, or None.

    The block is the key line plus the indented (or column-0 `- `) lines under it. Blank lines
    and column-0 comments after the last such line belong to what follows, not to the block.
    """
    start = next((i for i, line in enumerate(lines) if line.startswith(key + ":")), None)
    if start is None:
        return None
    end = start + 1
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if not line.strip() or line.startswith("#"):
            continue
        if line[0] in " \t" or line.startswith("- "):
            end = i + 1
        else:
            break
    return start, end


def replace_block(text, key, new_block):
    """`text` with the `key` block swapped for `new_block`. A missing key is appended."""
    new_lines = new_block.splitlines(keepends=True)
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"
    lines = text.splitlines(keepends=True)
    found = block_range(lines, key)
    if found is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        return "".join(lines + new_lines)
    start, end = found
    return "".join(lines[:start] + new_lines + lines[end:])


def edit_draft(repo, key, new_block):
    """Edit the draft (or a copy of plumber.yaml), save it, and report if it still loads."""
    from detect_case import load_error  # needs plumber, so import only when used

    repo = Path(repo)
    source = repo / DRAFT if (repo / DRAFT).exists() else repo / CONFIG
    text = source.read_text(encoding="utf-8") if source.exists() else ""
    draft = write_draft(repo, replace_block(text, key, new_block))
    return {"draft": str(draft), "error": load_error(draft)}


def main():
    repo, key = sys.argv[1], sys.argv[2]
    os.chdir(repo)  # plumber resolves phase paths from the working directory
    print(json.dumps(edit_draft(".", key, sys.stdin.read())))


if __name__ == "__main__":
    main()
