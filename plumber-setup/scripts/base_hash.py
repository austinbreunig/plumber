"""Hash text for the `# base:` line, in `plumber.yaml`, drafts and generated shims.

Run with any Python:
  python base_hash.py hash <file>    -> {"hash": "<hash>"}  ("none" if the file is missing)
  python base_hash.py check <file>   -> {"matches": true|false}
`check` compares the file's own line 1 `# base: <hash>` with a hash of the rest.
The `# base:` line is never part of the hash.
"""

import hashlib
import json
import sys
from pathlib import Path

PREFIX = "# base:"


def split_base(text):
    """(base value or None, text without the `# base:` first line)."""
    first, _, rest = text.partition("\n")
    if first.startswith(PREFIX):
        return first[len(PREFIX):].strip(), rest
    return None, text


def read_base(text):
    return split_base(text)[0]


def hash_text(text):
    return hashlib.sha256(split_base(text)[1].encode("utf-8")).hexdigest()[:16]


def hash_file(path):
    """Hash of the file, or "none" if it does not exist."""
    path = Path(path)
    return hash_text(path.read_text(encoding="utf-8")) if path.exists() else "none"


def base_matches(path):
    """True if the file's `# base:` line still matches its text (no hand edits)."""
    text = Path(path).read_text(encoding="utf-8")
    return read_base(text) == hash_text(text)


def main():
    command, path = sys.argv[1], sys.argv[2]
    if command == "hash":
        print(json.dumps({"hash": hash_file(path)}))
    else:
        print(json.dumps({"matches": base_matches(path)}))


if __name__ == "__main__":
    main()
