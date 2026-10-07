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
    config["execution"] = {"strategy": "local", "partition": {"worker_count": 4}}
    report = check(config)
    assert statuses(report)["partition"] == "FAIL"
    assert "worker_count" in messages(report, "partition")


def test_unknown_strategy_fails(project):
    config = good_config()
    config["execution"] = {"strategy": "warp-drive"}
    assert statuses(check(config))["strategy"] == "FAIL"


def localmp_config(**partition):
    config = good_config()
    config["execution"] = {"strategy": "localmp", "partition": partition}
    return config


def test_localmp_accepts_each_partition_key(project):
    for partition in ({"by": ["zone"]}, {"chunk_size": 4}, {"worker_count": 2}):
        assert check(localmp_config(**partition))["ok"], partition


def test_localmp_needs_exactly_one_partition_key(project):
    for partition in ({}, {"by": ["zone"], "chunk_size": 4}):
        report = check(localmp_config(**partition))
        assert statuses(report)["partition"] == "FAIL", partition


def test_localmp_partition_values_are_checked(project):
    for partition in ({"by": "zone"}, {"chunk_size": 0}, {"worker_count": "x"}):
        report = check(localmp_config(**partition))
        assert statuses(report)["partition"] == "FAIL", partition


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


# ---- runtime probe ----------------------------------------------------------------------


def probe_config(*phases, partitionable=True):
    """The good config with its phases replaced and a sample file configured."""
    from myio import load_fixture

    load_fixture().to_parquet("sample.parquet")
    config = good_config()
    config["phases"] = [
        {"path": f"phases.{name}:run", "partitionable": partitionable, "params": {}}
        for name in phases
    ]
    config["check"] = {"sample": "sample.parquet"}
    return config


def test_no_sample_leaves_result_unchanged(project):
    report = check(good_config())
    assert report["runtime_probe"] == "not run (no check.sample)"
    assert set(statuses(report).values()) == {"PASS"}


def test_good_phases_pass_the_probe(project):
    config = probe_config("scale_value")
    config["phases"][0]["params"] = {"factor": 2}
    report = check(config)
    assert report["ok"] is True
    assert statuses(report)["P1"] == "PASS"
    assert report["runtime_probe"] == "ran on sample.parquet"


def test_shared_state_in_partitionable_phase_fails(project):
    report = check(probe_config("counter_state"))
    assert statuses(report)["P1"] == "FAIL"
    assert "shared state" in messages(report, "P1")
    assert report["ok"] is False


def test_shared_state_is_not_checked_when_not_partitionable(project):
    report = check(probe_config("counter_state", partitionable=False))
    assert statuses(report)["P1"] == "PASS"


def test_crs_change_is_a_warning(project):
    report = check(probe_config("reproject"))
    assert statuses(report)["P1"] == "WARN"
    assert "CRS" in messages(report, "P1")
    assert report["ok"] is True


def test_dropped_column_is_a_warning(project):
    report = check(probe_config("drop_value"))
    assert statuses(report)["P1"] == "WARN"
    assert "value" in messages(report, "P1")


def test_crash_fails_and_skips_later_phases(project):
    report = check(probe_config("reproject", "crash", "reproject"))
    assert statuses(report)["P2"] == "FAIL"
    assert "zone_id" in messages(report, "P2")
    assert statuses(report)["P3"] == "SKIP"
    assert report["ok"] is False


def test_skip_status_is_written_to_report_json(project):
    from plumber.check import write_report

    write_report(check(probe_config("crash", "reproject")))
    rows = json.loads(Path("report.json").read_text())["rows"]
    assert {row["label"]: row["status"] for row in rows}["P2"] == "SKIP"


def test_missing_sample_file_fails(project):
    config = good_config()
    config["check"] = {"sample": "nope.parquet"}
    report = check(config)
    assert statuses(report)["check.sample"] == "FAIL"


def test_probe_does_not_run_when_static_checks_fail(project):
    config = probe_config("scale_value")
    config["phases"][0]["path"] = "phases.nope:run"
    report = check(config)
    assert "not run" in report["runtime_probe"]


def test_run_preflight_never_runs_the_probe(project):
    config = probe_config("counter_state")
    config["output"] = None
    with pytest.warns(UserWarning):  # no output: result discarded
        run(config)  # the probe would FAIL counter_state; run must not probe


# ---- review fixes -----------------------------------------------------------------------


def test_checkpoints_block_without_dir_passes(project):
    config = probe_config("scale_value")
    config["checkpoints"] = {}
    assert check(config)["ok"]


def test_missing_input_is_a_fail(project):
    config = probe_config("scale_value")
    del config["input"]
    report = check(config)
    assert not report["ok"]
    assert any(row["label"] == "input" and row["status"] == "FAIL" for row in report["rows"])
