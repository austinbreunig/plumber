"""Find the target repo's venv and check its plumber version.

Run with any Python: `python find_venv.py <repo>`. Prints JSON:
  {"status": "ok", "venv": "..."}                    use this venv
  {"status": "ask", "candidates": ["...", "..."]}    several work, ask the user
  {"status": "stop", "reason": "...", "fix": "..."}  tell the user the fix, install nothing
"""

import json
import os
import subprocess
import sys
from pathlib import Path

MIN_PLUMBER_VERSION = "0.1.2"

SKIP_DIRS = {".git", "node_modules", "__pycache__"}


def version_tuple(version):
    """'0.1.2' -> (0, 1, 2). Stops at the first non-number part ('0.1.2.dev1' -> (0, 1, 2))."""
    numbers = []
    for part in version.split("."):
        if not part.isdigit():
            break
        numbers.append(int(part))
    return tuple(numbers)


def version_at_least(version, minimum):
    return version_tuple(version) >= version_tuple(minimum)


def find_venvs(repo):
    """Every folder under `repo` that holds a `pyvenv.cfg`."""
    found = []
    for folder, subdirs, files in os.walk(repo):
        if "pyvenv.cfg" in files:
            found.append(Path(folder))
            subdirs[:] = []  # do not look inside a venv
        else:
            subdirs[:] = [d for d in subdirs if d not in SKIP_DIRS]
    return found


def venv_python(venv):
    posix = Path(venv) / "bin" / "python"
    return posix if posix.exists() else Path(venv) / "Scripts" / "python.exe"


def plumber_version(venv):
    """The plumber version installed in `venv`, or None if it cannot be imported."""
    code = "import plumber; print(plumber.__version__)"
    try:
        done = subprocess.run(
            [str(venv_python(venv)), "-c", code], capture_output=True, text=True, timeout=60
        )
    except OSError:
        return None
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def is_inside(path, folder):
    try:
        Path(path).resolve().relative_to(Path(folder).resolve())
    except ValueError:
        return False
    return True


def is_same(a, b):
    return Path(a).resolve() == Path(b).resolve()


def pick_venv(repo, virtual_env=None):
    """Choose the venv to use. See the module docstring for the result shapes."""
    candidates = find_venvs(repo)
    if virtual_env and is_inside(virtual_env, repo):
        active = Path(virtual_env)
        if active not in candidates and (active / "pyvenv.cfg").exists():
            candidates.append(active)
    if not candidates:
        return {
            "status": "stop",
            "reason": f"no venv (pyvenv.cfg) found under {repo}",
            "fix": "uv venv && uv add ab-plumber",
        }

    versions = {venv: plumber_version(venv) for venv in candidates}
    working = [v for v, version in versions.items() if version]
    if not working:
        return {
            "status": "stop",
            "reason": "plumber is not installed in any venv found",
            "fix": "uv add ab-plumber",
        }
    new_enough = [v for v in working if version_at_least(versions[v], MIN_PLUMBER_VERSION)]
    if not new_enough:
        old = ", ".join(f"{v} has {versions[v]}" for v in working)
        return {
            "status": "stop",
            "reason": f"plumber is too old (need {MIN_PLUMBER_VERSION} or newer): {old}",
            "fix": f'uv add "ab-plumber>={MIN_PLUMBER_VERSION}"',
        }

    if virtual_env:
        active = next((v for v in new_enough if is_same(v, virtual_env)), None)
        if active:
            return {"status": "ok", "venv": str(active)}
    if len(new_enough) == 1:
        return {"status": "ok", "venv": str(new_enough[0])}
    return {"status": "ask", "candidates": [str(v) for v in new_enough]}


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    print(json.dumps(pick_venv(repo, os.environ.get("VIRTUAL_ENV"))))


if __name__ == "__main__":
    main()
