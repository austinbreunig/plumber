import shutil
import sys
from pathlib import Path

import geopandas as gpd
import pytest
import yaml

from plumber import run as run_module
from plumber.checkpoint import checkpoint_path, read_checkpoint
from plumber.cli import main
from plumber.local import LocalSequential

FIXTURE = Path(__file__).parent / "fixture"
# Fixture phases, in order: scale_value, dedupe_zone_leader, tag_percentile.


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A copy of the fixture where scale_value and dedupe_zone_leader save checkpoints."""
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    config = yaml.safe_load((tmp_path / "plumber.yaml").read_text())
    names = ["scale_value", "dedupe_zone_leader", "tag_percentile"]
    for phase, name in zip(config["phases"], names):
        phase["name"] = name
    config["phases"][0]["checkpoint"] = True
    config["phases"][1]["checkpoint"] = True
    (tmp_path / "plumber.yaml").write_text(yaml.safe_dump(config))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    return tmp_path


class Spy(LocalSequential):
    """A normal strategy that remembers the call it got."""

    def execute(self, input, steps, output, run_params):
        self.call = (input, [step.name for step in steps], output)
        return super().execute(input, steps, output, run_params)


@pytest.fixture
def spy(monkeypatch):
    strategy = Spy()
    monkeypatch.setattr(run_module, "build_strategy", lambda config: strategy)
    return strategy


def test_from_starts_at_previous_checkpoint(project, spy, capsys):
    main(["run", "--to", "dedupe_zone_leader"])  # saves the checkpoints
    (project / "out").mkdir(exist_ok=True)
    with pytest.warns(UserWarning, match=r"Starting at tag_percentile from checkpoint "
                                         r"dedupe_zone_leader\.parquet \(saved \d{4}-\d\d-\d\d "):
        main(["run", "--from", "tag_percentile"])
    input_pair, names, output = spy.call
    assert input_pair[0] is read_checkpoint
    assert input_pair[1]["name"] == "dedupe_zone_leader"
    assert names == ["tag_percentile"]
    assert output is not None
    out = gpd.read_parquet(project / "out" / "result.parquet")
    assert out["id"].tolist() == [9, 10, 11]
    assert out["high"].tolist() == [False, True, True]


def test_from_missing_checkpoint_fails_hard_with_fix(project, spy):
    with pytest.raises(SystemExit) as error:
        main(["run", "--from", "tag_percentile"])
    message = str(error.value)
    assert "dedupe_zone_leader" in message
    assert "checkpoint: true" in message
    assert not hasattr(spy, "call")  # nothing ran


def test_from_first_phase_uses_the_input_function(project, spy):
    main(["run", "--from", "scale_value"])
    input_pair, names, output = spy.call
    assert input_pair[0].__name__ == "load_fixture"
    assert names == ["scale_value", "dedupe_zone_leader", "tag_percentile"]
    assert output is not None


def test_to_skips_output_and_keeps_the_checkpoint(project, spy):
    main(["run", "--to", "dedupe_zone_leader"])
    _, names, output = spy.call
    assert names == ["scale_value", "dedupe_zone_leader"]
    assert output is None
    assert not (project / "out").exists()
    assert read_checkpoint(".plumber/checkpoints", "dedupe_zone_leader")["id"].tolist() == [
        9,
        10,
        11,
    ]


def test_to_last_phase_runs_output_without_warning(project, spy, recwarn):
    main(["run", "--to", "tag_percentile"])
    assert not [w for w in recwarn if "result discarded" in str(w.message)]
    assert (project / "out" / "result.parquet").exists()


def test_to_middle_phase_without_checkpoint_warns_and_runs(project, spy):
    config = yaml.safe_load((project / "plumber.yaml").read_text())
    config["phases"][0]["checkpoint"] = False
    (project / "plumber.yaml").write_text(yaml.safe_dump(config))
    with pytest.warns(UserWarning, match="result discarded"):
        main(["run", "--to", "scale_value"])
    assert spy.call[1] == ["scale_value"]
    assert spy.call[2] is None
    assert not checkpoint_path(".plumber/checkpoints", "scale_value").exists()


def test_from_and_to_select_one_phase(project, spy):
    main(["run", "--to", "dedupe_zone_leader"])
    with pytest.warns(UserWarning, match="Starting at dedupe_zone_leader"):
        main(["run", "--from", "dedupe_zone_leader", "--to", "dedupe_zone_leader"])
    assert spy.call[1] == ["dedupe_zone_leader"]
    assert spy.call[2] is None


def test_unknown_or_backwards_names_fail(project, spy):
    with pytest.raises(SystemExit, match="nope"):
        main(["run", "--from", "nope"])
    with pytest.raises(SystemExit, match="nope"):
        main(["run", "--to", "nope"])
    with pytest.raises(SystemExit, match="after"):
        main(["run", "--from", "tag_percentile", "--to", "scale_value"])


def test_check_still_validates_full_config_when_slicing(project, spy):
    config = yaml.safe_load((project / "plumber.yaml").read_text())
    config["phases"][2]["path"] = "phases.missing_module:run"  # broken, outside the slice
    (project / "plumber.yaml").write_text(yaml.safe_dump(config))
    with pytest.raises(SystemExit, match="check failed"):
        main(["run", "--to", "scale_value"])
