import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

SKILL_SCRIPTS = Path(__file__).parents[2] / "plumber-setup" / "scripts"
FIXTURE_REPO = Path(__file__).parent / "fixtures" / "repo"


def load_helper(name):
    """Import a skill helper by file path (the skill folder is not a package)."""
    spec = importlib.util.spec_from_file_location(f"skill_{name}", SKILL_SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def forget_repo_modules():
    """Drop the fixture's `phases`/`myio` modules so other tests' fixtures import their own."""
    for name in list(sys.modules):
        if name in ("myio", "phases") or name.startswith("phases."):
            del sys.modules[name]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A copy of the fixture repo; cwd is the repo, as the skill runs helpers."""
    shutil.copytree(FIXTURE_REPO, tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    forget_repo_modules()
    yield tmp_path
    forget_repo_modules()
