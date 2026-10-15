import logging
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

from plumber.cli import main
from plumber.local import LocalSequential
from plumber.localmp import LocalMultiprocess
from plumber.protocols import Step, plumber_log

FIXTURE = Path(__file__).parent / "fixture"


def chatty(data):
    """Logs at every level from a user logger and from a library-style logger."""
    for name in ("my.phase", "pyproj.crs"):
        log = logging.getLogger(name)
        for level in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR):
            log.log(level, "%s %s", name, logging.getLevelName(level))
    return data


def run_chatty(caplog, **run_params):
    """The Run log lines from `execute`, as (logger name, text)."""
    caplog.set_level(logging.DEBUG)
    step = Step("chatty", chatty, {}, partitionable=False, checkpoint=False)
    LocalSequential().execute((lambda: [1], {}), [step], None, run_params)
    return [(r.name, r.getMessage()) for r in caplog.records]


def user_lines(lines):
    return [text.split("] ", 1)[1] for name, text in lines if name != "plumber"]


def plumber_lines(lines):
    return [text for name, text in lines if name == "plumber"]


def test_default_level_is_info(caplog):
    lines = run_chatty(caplog)
    assert "my.phase DEBUG" not in user_lines(lines)
    assert "my.phase INFO" in user_lines(lines)


def test_user_level_hides_lines_below_it(caplog):
    lines = run_chatty(caplog, user_level="WARNING")
    assert user_lines(lines) == [
        "my.phase WARNING",
        "my.phase ERROR",
        "pyproj.crs WARNING",
        "pyproj.crs ERROR",
    ]


def test_debug_shows_everything(caplog):
    assert len(user_lines(run_chatty(caplog, user_level="debug"))) == 8


def test_off_silences_user_log_but_not_plumber_log(caplog):
    lines = run_chatty(caplog, user_level="off")
    assert user_lines(lines) == []
    assert plumber_lines(lines) == [
        "=== input ===",
        "=== end input: ok ===",
        "=== phase chatty ===",
        "=== end chatty: ok ===",
    ]


@pytest.mark.parametrize("level", ["DEBUG", "ERROR", "off"])
def test_plumber_log_shows_at_every_level(caplog, level):
    assert "=== phase chatty ===" in plumber_lines(run_chatty(caplog, user_level=level))


def test_root_level_is_restored_after_execute(caplog):
    caplog.set_level(logging.DEBUG)
    run_chatty(caplog, user_level="ERROR")
    assert logging.getLogger().level == logging.DEBUG


@pytest.fixture
def project(tmp_path, monkeypatch):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))


def cli_lines(caplog, *argv):
    caplog.set_level(logging.DEBUG)
    main(["run", *argv])
    return [r.getMessage() for r in caplog.records]


def set_config_level(level):
    config = yaml.safe_load(Path("plumber.yaml").read_text())
    config["user_level"] = level
    Path("plumber.yaml").write_text(yaml.safe_dump(config))


def test_config_user_level_filters(project, caplog):
    set_config_level("off")
    assert not [line for line in cli_lines(caplog) if "scaling by" in line]


def test_cli_user_level_wins_over_config(project, caplog):
    set_config_level("off")
    assert [line for line in cli_lines(caplog, "--user-level", "INFO") if "scaling by" in line]


@pytest.mark.parametrize("command", ["run", "check"])
def test_bad_level_name_fails_clearly(project, command, capsys):
    with pytest.raises(SystemExit):
        main([command, "--user-level", "LOUD"])
    assert "'LOUD' is not a level" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["run", "check"])
def test_bad_level_name_in_config_fails(project, command, capsys):
    set_config_level("LOUD")
    with pytest.raises(SystemExit) as stopped:
        main([command])
    shown = str(stopped.value) + capsys.readouterr().out
    assert "user_level" in shown and "'LOUD' is not a level" in shown


def test_localmp_workers_follow_user_level_under_each_start_method(caplog, start_method):
    caplog.set_level(logging.DEBUG)
    step = Step("chatty", chatty, {}, partitionable=True, checkpoint=False)
    data = pd.DataFrame({"id": range(4)})
    LocalMultiprocess({"chunk_size": 1}).execute(
        (lambda: data, {}), [step], None, {"user_level": "ERROR"}
    )
    lines = [(r.name, r.getMessage()) for r in caplog.records]
    assert set(user_lines(lines)) == {"my.phase ERROR", "pyproj.crs ERROR"}
    assert "=== phase chatty ===" in plumber_lines(lines)


def write_raw_off():
    text = Path("plumber.yaml").read_text()
    Path("plumber.yaml").write_text(text + "\nuser_level: off\n")  # unquoted: YAML reads False


def test_unquoted_off_in_config_silences_user_log(project, caplog):
    write_raw_off()
    assert not [line for line in cli_lines(caplog) if "scaling by" in line]


def test_unquoted_off_in_config_passes_check(project, capsys):
    write_raw_off()
    main(["check"])
    assert "user_level" not in capsys.readouterr().out


def test_plumber_debug_lines_show_when_user_level_is_high(caplog):
    caplog.set_level(logging.DEBUG)
    step = Step("noisy", lambda data: plumber_log.debug("deep detail") or data, {}, False, False)
    LocalSequential().execute((lambda: [1], {}), [step], None, {"user_level": "ERROR"})
    assert "deep detail" in plumber_lines([(r.name, r.getMessage()) for r in caplog.records])
