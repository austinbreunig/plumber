"""Edit or remove a skill-made shim in `.plumber/`. Run with any Python; prints JSON.

  python shim_edit.py status <repo> <name>
      -> {"exists", "skill_made", "hand_edited", "text"}
  python shim_edit.py diff <repo> < spec.json
      -> {"diff": "<unified diff old vs new, empty if no change>"}
  python shim_edit.py edit <repo> [overwrite|keep|stop] < spec.json
      -> {"status": "written" | "kept" | "not_skill_made" | "missing"}
  python shim_edit.py remove <repo> <name> [overwrite]
      -> {"status": "removed" | "in_use" | "hand_edited" | "not_skill_made" | "missing",
          "used_by": [...]}
The spec is the same JSON as `render_shim.py`.
Only files whose line 2 starts with `# shim wraps` are ever changed or deleted.
A shim whose `# base:` hash does not match its text was hand-edited: it needs "overwrite".
A shim that `plumber.yaml` or the draft still names (`<name>:run`) is not removed.
"""

import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from base_hash import base_matches  # noqa: E402
from render_shim import SHIM_DIR, check_identifier, render_shim  # noqa: E402

WRAPS_PREFIX = "# shim wraps"
CONFIG_FILES = ["plumber.draft.yaml", "plumber.yaml"]


def shim_path(repo, name):
    return Path(repo) / SHIM_DIR / f"{check_identifier(name)}.py"


def shim_status(repo, name):
    path = shim_path(repo, name)
    if not path.exists():
        return {"exists": False, "skill_made": False, "hand_edited": False, "text": ""}
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    skill_made = len(lines) > 1 and lines[1].startswith(WRAPS_PREFIX)
    return {
        "exists": True,
        "skill_made": skill_made,
        "hand_edited": skill_made and not base_matches(path),
        "text": text,
    }


def used_by(repo, name):
    """Config files in the repo root that still point a phase at `<name>:...`."""
    pattern = re.compile(rf"(?<![\w.]){re.escape(name)}:")
    return [
        f for f in CONFIG_FILES
        if (Path(repo) / f).exists() and pattern.search((Path(repo) / f).read_text("utf-8"))
    ]


def edit_diff(repo, spec):
    """Unified diff of the shim on disk against the shim the new spec renders."""
    old = shim_status(repo, spec["name"])["text"]
    new = render_shim(spec)
    return "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True), "old", "new"
    ))


def apply_edit(repo, spec, choice=None):
    """Rewrite the shim. A hand-edited one is only rewritten when choice is "overwrite"."""
    status = shim_status(repo, spec["name"])
    if not status["exists"]:
        return {"status": "missing"}
    if not status["skill_made"]:
        return {"status": "not_skill_made"}
    if status["hand_edited"] and choice != "overwrite":
        return {"status": "kept"}
    shim_path(repo, spec["name"]).write_text(render_shim(spec), encoding="utf-8")
    return {"status": "written"}


def remove_shim(repo, name, choice=None):
    """Delete a skill-made shim. Refuses hand-written, in-use, or hand-edited (unless overwrite)."""
    status = shim_status(repo, name)
    if not status["exists"]:
        return {"status": "missing"}
    if not status["skill_made"]:
        return {"status": "not_skill_made"}
    users = used_by(repo, name)
    if users:
        return {"status": "in_use", "used_by": users}
    if status["hand_edited"] and choice != "overwrite":
        return {"status": "hand_edited"}
    shim_path(repo, name).unlink()
    return {"status": "removed"}


def main():
    command, repo = sys.argv[1], sys.argv[2]
    extra = sys.argv[3:]
    if command == "status":
        print(json.dumps(shim_status(repo, extra[0])))
    elif command == "diff":
        print(json.dumps({"diff": edit_diff(repo, json.load(sys.stdin))}))
    elif command == "edit":
        print(json.dumps(apply_edit(repo, json.load(sys.stdin), *extra)))
    else:
        print(json.dumps(remove_shim(repo, *extra)))


if __name__ == "__main__":
    main()
