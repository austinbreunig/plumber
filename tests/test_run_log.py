import logging
import shutil
import sys
from pathlib import Path

import pytest
import yaml

from plumber.cli import main

FIXTURE = Path(__file__).parent / "fixture"
SCALE = "phases.scale_value:run"
DEDUPE = "phases.dedupe_zone_leader:run"
TAG = "phases.tag_percentile:run"


@pytest.fixture
def project(tmp_path, monkeypatch):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))


def run_log(caplog, *argv):
    """The Run log of `plumber run`, one string per line."""
    caplog.set_level(logging.INFO)
    main(["run", *argv])
    return [record.getMessage() for record in caplog.records]


def test_local_run_reads_phase_by_phase(project, caplog):
    lines = run_log(caplog)

    assert lines[0] == "=== run start: 3 phases ==="
    assert lines[-1] == "=== run end ==="
    # The user's own log line sits inside its phase, tagged [phase|process].
    assert lines[lines.index(f"=== phase {SCALE} ===") + 1] == (
        f"[{SCALE}|MainProcess] scaling by 2"
    )
    for name in (SCALE, DEDUPE, TAG):
        assert f"=== phase {name} ===" in lines
        assert f"=== end {name}: ok ===" in lines
    order = [lines.index(f"=== phase {name} ===") for name in (SCALE, DEDUPE, TAG)]
    assert order == sorted(order)
    assert lines.index(f"=== end {SCALE}: ok ===") < lines.index(f"=== phase {DEDUPE} ===")


def test_input_and_output_get_a_heading_too(project, caplog):
    lines = run_log(caplog)

    assert lines[1:3] == ["=== input ===", "=== end input: ok ==="]
    assert lines[-3:-1] == ["=== output ===", "=== end output: ok ==="]


def test_partial_run_only_shows_phases_that_ran(project, caplog):
    lines = run_log(caplog, "--to", SCALE)

    assert lines[0] == "=== run start: 1 phases ==="
    assert f"=== phase {DEDUPE} ===" not in lines


def test_crashing_phase_still_gets_a_closing_line(project, caplog):
    config = yaml.safe_load(Path("plumber.yaml").read_text())
    config["phases"][1]["path"] = "phases.crash:run"
    Path("plumber.yaml").write_text(yaml.safe_dump(config))
    caplog.set_level(logging.INFO)

    with pytest.raises(KeyError):
        main(["run"])

    lines = [record.getMessage() for record in caplog.records]
    assert "=== end phases.crash:run: failed ===" in lines
    assert "=== run end ===" not in lines


def headings(lines):
    return [line for line in lines if line.startswith("===")]


def test_localmp_run_log_matches_local_under_each_start_method(project, caplog, start_method):
    local = run_log(caplog)
    caplog.clear()
    mp = run_log(caplog, "--strategy", "localmp", "--chunk-size", "2")

    assert headings(mp) == headings(local)


def test_localmp_worker_lines_sit_in_their_phase_tagged_by_worker(project, caplog, start_method):
    lines = run_log(caplog, "--strategy", "localmp", "--chunk-size", "1")

    start = lines.index(f"=== phase {SCALE} ===")
    end = lines.index(f"=== end {SCALE}: ok ===")
    worker_lines = [line for line in lines if line.endswith("scaling by 2")]
    assert len(worker_lines) > 1  # one per piece
    for line in worker_lines:
        assert start < lines.index(line) < end
        assert line.startswith(f"[{SCALE}|") and "MainProcess" not in line
        assert line.count("[") == 1  # tagged once
    # Everything before the next heading: phase N is fully delivered first.
    assert end < lines.index(f"=== phase {DEDUPE} ===")


def checkpoint_scale(strategy=None):
    config = yaml.safe_load(Path("plumber.yaml").read_text())
    config["phases"][0]["checkpoint"] = True
    if strategy:
        config["execution"] = {"strategy": strategy, "partition": {"worker_count": 2}}
    Path("plumber.yaml").write_text(yaml.safe_dump(config))


def saved_line_is_under_scale(lines):
    saved = [i for i, line in enumerate(lines) if line.startswith("checkpoint saved: ")]
    assert len(saved) == 1
    assert lines[saved[0]].endswith(f"{SCALE}.parquet")
    start = lines.index(f"=== phase {SCALE} ===")
    assert start < saved[0] < lines.index(f"=== end {SCALE}: ok ===")


def test_checkpoint_saved_line_sits_under_its_phase_in_local(project, caplog):
    checkpoint_scale()
    saved_line_is_under_scale(run_log(caplog))


def test_checkpoint_saved_line_sits_under_its_phase_in_localmp(project, caplog):
    checkpoint_scale("localmp")
    saved_line_is_under_scale(run_log(caplog))


def test_from_to_shows_headings_only_for_phases_that_ran(project, caplog):
    checkpoint_scale()
    main(["run", "--to", SCALE])
    caplog.clear()
    lines = run_log(caplog, "--from", DEDUPE, "--to", DEDUPE)

    assert [line for line in lines if line.startswith("=== phase")] == [f"=== phase {DEDUPE} ==="]
