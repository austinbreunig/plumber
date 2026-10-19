"""Small things the helpers share: file names and the repo walk."""

import os
from pathlib import Path

CONFIG = "plumber.yaml"
DRAFT = "plumber.draft.yaml"


def walk_repo(repo, skip_dir):
    """Yield (folder, files, is_venv) under `repo`. Never looks inside a venv (`pyvenv.cfg`)
    or into a subfolder for which `skip_dir(name)` is true."""
    for folder, subdirs, files in os.walk(repo):
        is_venv = "pyvenv.cfg" in files
        subdirs[:] = [] if is_venv else sorted(d for d in subdirs if not skip_dir(d))
        yield Path(folder), files, is_venv
