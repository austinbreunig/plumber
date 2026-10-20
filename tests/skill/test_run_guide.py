import re

import pytest

from conftest import SKILL_SCRIPTS
from plumber.cli import main

RUN_GUIDE = SKILL_SCRIPTS.parent / "run-guide.md"


def cli_help(command, capsys):
    with pytest.raises(SystemExit):
        main([command, "--help"])
    return capsys.readouterr().out


def test_run_guide_flags_exist_in_cli(capsys):
    """Every `--flag` in the run guide is in the live CLI help, so the guide cannot drift."""
    flags = set(re.findall(r"--[a-z][a-z-]*", RUN_GUIDE.read_text()))
    assert flags, "run guide mentions no flags"
    known = cli_help("run", capsys) + cli_help("check", capsys)
    missing = sorted(flag for flag in flags if flag not in known)
    assert not missing, f"flags not in `plumber run --help` or `plumber check --help`: {missing}"
