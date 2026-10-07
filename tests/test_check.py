import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

from plumber.check import check
from plumber.cli import main
from plumber.run import run

FIXTURE = Path(__file__).parent / "fixture"


@pytest.fixture
def project(tmp_path, monkeypatch):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    return tmp_path


def good_config():
    return yaml.safe_load((FIXTURE / "plumber.yaml").read_text())


def statuses(report):
    return {row["label"]: row["status"] for row in report["rows"]}


def messages(report, label):
    row = next(r for r in report["rows"] if r["label"] == label)
    return " ".join(row["messages"])


def test_good_config_passes_everywhere(project):
    report = check(good_config())
    assert statuses(report) == {
        "input": "PASS",
        "P1": "PASS",
        "P2": "PASS",
        "P3": "PASS",
        "output": "PASS",
    }
    assert report["ok"] is True


def test_bad_path_fails_only_that_phase(project):
    config = good_config()
    config["phases"][0]["path"] = "phases.nope:run"
    report = check(config)
    assert statuses(report)["P1"] == "FAIL"
    assert statuses(report)["P2"] == "PASS"
    assert report["ok"] is False


def test_path_without_attr_fails(project):
    config = good_config()
    config["phases"][0]["path"] = "phases.scale_value"
    assert statuses(check(config))["P1"] == "FAIL"


def test_missing_attr_in_module_fails(project):
    config = good_config()
    config["phases"][0]["path"] = "phases.scale_value:missing"
    assert statuses(check(config))["P1"] == "FAIL"


def test_missing_partitionable_fails(project):
    config = good_config()
    del config["phases"][1]["partitionable"]
    report = check(config)
    assert statuses(report)["P2"] == "FAIL"
    assert "partitionable" in messages(report, "P2")


def test_checkpoint_must_be_bool(project):
    config = good_config()
    config["phases"][0]["checkpoint"] = "yes"
    assert statuses(check(config))["P1"] == "FAIL"


def test_malformed_checkpoints_block_fails(project):
    config = good_config()
    config["checkpoints"] = {"dir": 5}
    assert statuses(check(config))["checkpoints"] == "FAIL"


def test_param_the_signature_does_not_accept_fails(project):
    config = good_config()
    config["input"]["params"] = {"by_zone": True}  # load_fixture() takes no params
    report = check(config)
    assert statuses(report)["input"] == "FAIL"
    assert "by_zone" in messages(report, "input")


def test_phase_with_var_kwargs_accepts_any_param(project):
    config = good_config()
    config["phases"][1]["params"] = {"anything": 1}  # dedupe_zone_leader has **params
    assert statuses(check(config))["P2"] == "PASS"


def test_required_param_missing_fails(project):
    config = good_config()
    config["output"]["params"] = {}  # write_parquet(gdf, path) needs path
    report = check(config)
    assert statuses(report)["output"] == "FAIL"
    assert "path" in messages(report, "output")


def test_partition_key_unused_by_strategy_fails(project):
    config = good_config()
    config["partition"] = {"worker_count": 4}
    report = check(config)
    assert statuses(report)["partition"] == "FAIL"
    assert "worker_count" in messages(report, "partition")


def test_unknown_strategy_fails(project):
    config = good_config()
    config["strategy"] = "warp-drive"
    assert statuses(check(config))["strategy"] == "FAIL"


def test_typo_in_config_params_fails(project):
    config = good_config()
    config["phases"][0] = {
        "path": "phases.strict_by:run",
        "partitionable": True,
        "params": {"bye": 1},
    }
    report = check(config)
    assert statuses(report)["P1"] == "FAIL"
    assert "bye" in messages(report, "P1")


def test_unknown_cli_param_warns_but_does_not_fail(project):
    report = check(good_config(), {"typo_key": 1})
    assert statuses(report)["--params"] == "WARN"
    assert report["ok"] is True


def test_known_cli_param_does_not_warn(project):
    report = check(good_config(), {"factor": 3})
    assert "--params" not in statuses(report)


def test_check_command_prints_lines_and_writes_report_json(project, capsys):
    main(["check"])
    out = capsys.readouterr().out
    assert "phases.scale_value:run" in out
    assert "PASS" in out
    assert "runtime probe: not run (no check.sample)" in out
    saved = json.loads((project / "report.json").read_text())
    assert saved["ok"] is True
    assert [r["label"] for r in saved["rows"]] == ["input", "P1", "P2", "P3", "output"]


def test_check_command_accepts_params_and_warns_on_typo(project, capsys):
    main(["check", "--params", "typo_key=1"])
    assert "WARN" in capsys.readouterr().out


def test_check_command_exits_nonzero_on_fail(project):
    config = good_config()
    config["phases"][0]["path"] = "phases.nope:run"
    (project / "plumber.yaml").write_text(yaml.safe_dump(config))
    with pytest.raises(SystemExit) as exc:
        main(["check"])
    assert exc.value.code == 1


def test_run_preflight_blocks_on_fail_and_runs_nothing(project):
    config = good_config()
    config["phases"][0]["path"] = "phases.nope:run"
    with pytest.raises(SystemExit):
        run(config)
    assert not (project / "out").exists()


def test_run_preflight_does_not_block_on_warn(project):
    with pytest.warns(UserWarning):
        run(good_config(), {"typo_key": 1})
    assert (project / "out" / "result.parquet").exists()
