import os
import shutil
import sys
from pathlib import Path

import geopandas as gpd
import pytest
import yaml

from plumber.cli import main
from plumber.run import build_steps, run

FIXTURE = Path(__file__).parent / "fixture"


@pytest.fixture
def project(tmp_path, monkeypatch):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    return tmp_path


def phase(path="phases.scale_value:run", **extra):
    return {"path": path, "partitionable": True, **extra}


def test_cli_params_win_over_config_with_shallow_merge(project):
    config = {"phases": [phase(params={"distance_m": 50, "cap": "round"})]}
    [step] = build_steps(config, {"distance_m": 100})
    assert step.params == {"distance_m": 100, "cap": "round"}


def test_cli_param_replaces_whole_value_no_deep_merge(project):
    config = {"phases": [phase(params={"opts": {"a": 1, "b": 2}})]}
    [step] = build_steps(config, {"opts": {"a": 9}})
    assert step.params == {"opts": {"a": 9}}


def test_override_only_reaches_phases_that_have_that_param(project):
    config = {"phases": [phase(params={"factor": 2}), phase("phases.tag_percentile:run")]}
    first, second = build_steps(config, {"factor": 5})
    assert first.params == {"factor": 5}
    assert second.params == {}


def test_override_matching_no_phase_is_silently_ignored(project):
    config = {"phases": [phase(params={"factor": 2})]}
    [step] = build_steps(config, {"nope": 1})
    assert step.params == {"factor": 2}


@pytest.mark.parametrize("block", ["input", "output"])
def test_run_rejects_io_path_without_attr(project, block):
    config = yaml.safe_load((project / "plumber.yaml").read_text())
    config[block]["path"] = "myio"
    with pytest.raises(ValueError, match="':attr' is required"):
        run(config)


def test_name_defaults_to_path_and_phases_keep_config_order(project):
    config = {
        "phases": [phase("phases.scale_value:run"), phase("phases.tag_percentile:run", name="tag")]
    }
    steps = build_steps(config, {})
    assert [s.name for s in steps] == ["phases.scale_value:run", "tag"]


def test_duplicate_names_are_a_hard_error_naming_both_entries(project):
    config = {"phases": [phase(), phase(params={"factor": 3})]}
    with pytest.raises(ValueError, match=r"phases\.scale_value:run.*entries 1 and 2"):
        build_steps(config, {})


def test_same_module_twice_works_with_distinct_names(project):
    config = {"phases": [phase(name="small"), phase(name="large")]}
    assert [s.name for s in build_steps(config, {})] == ["small", "large"]


def test_missing_output_warns_result_discarded_and_still_runs(project):
    config = yaml.safe_load((project / "plumber.yaml").read_text())
    del config["output"]
    with pytest.warns(UserWarning, match="result discarded"):
        result = run(config)
    assert len(result.collect()) == 3
    assert not (project / "out").exists()


def test_params_flag_changes_the_run(project):
    main(["run", "--params", "factor=5"])
    out = gpd.read_parquet(project / "out" / "result.parquet")
    assert out["value"].tolist() == [15, 50, 85]


def test_config_flag_loads_another_file(project):
    other = project / "elsewhere.yaml"
    (project / "plumber.yaml").rename(other)
    main(["run", "--config", str(other)])
    assert (project / "out" / "result.parquet").exists()


def test_default_config_is_only_the_current_folder(project):
    sub = project / "sub"
    sub.mkdir()
    os.chdir(sub)
    with pytest.raises(FileNotFoundError):
        main(["run"])
