import shutil
import sys
from pathlib import Path

import geopandas as gpd
import pytest
import yaml
from geopandas.testing import assert_geodataframe_equal
from shapely.geometry import Point

from plumber.checkpoint import checkpoint_path, read_checkpoint
from plumber.cli import main
from plumber.local import LocalSequential
from plumber.localmp import LocalMultiprocess
from plumber.protocols import Step

FIXTURE = Path(__file__).parent / "fixture"


def load():
    return gpd.GeoDataFrame(
        {"id": range(10), "zone": ["a", "b"] * 5},
        geometry=[Point(i, i) for i in range(10)],
        crs="EPSG:4326",
    )


def add(data, amount):
    data = data.copy()
    data["id"] = data["id"] + amount
    return data


def keep_even(data):
    return data[data["id"] % 2 == 0]


def steps():
    return [
        Step("add", add, {"amount": 1}, True, True),
        Step("even", keep_even, {}, False, False),
        Step("add2", add, {"amount": 10}, True, False),
    ]


STRATEGIES = [LocalSequential(), LocalMultiprocess({"by": ["zone"]})]
IDS = ["local", "localmp"]


@pytest.mark.parametrize("strategy", STRATEGIES, ids=IDS)
def test_checkpoint_phase_writes_geoparquet_in_dir(tmp_path, strategy):
    strategy.execute((load, {}), steps(), None, {"checkpoint_dir": str(tmp_path)})
    saved = read_checkpoint(tmp_path, "add")
    assert checkpoint_path(tmp_path, "add") == tmp_path / "add.parquet"
    assert saved["id"].tolist() == list(range(1, 11))  # after phase "add", in input order
    assert list(saved.columns) == ["id", "zone", "geometry"]
    assert saved.crs == "EPSG:4326"
    assert not (tmp_path / "even.parquet").exists()  # only opted-in phases


@pytest.mark.parametrize("strategy", STRATEGIES, ids=IDS)
def test_checkpoint_is_overwritten_each_run(tmp_path, strategy):
    params = {"checkpoint_dir": str(tmp_path)}
    strategy.execute((load, {}), steps(), None, params)
    changed = [Step("add", add, {"amount": 5}, True, True)]
    strategy.execute((load, {}), changed, None, params)
    assert read_checkpoint(tmp_path, "add")["id"].tolist() == list(range(5, 15))


def test_checkpoint_is_equal_under_both_strategies(tmp_path):
    for name, strategy in zip(["local", "mp"], STRATEGIES):
        strategy.execute((load, {}), steps(), None, {"checkpoint_dir": str(tmp_path / name)})
    local = read_checkpoint(tmp_path / "local", "add")
    mp = read_checkpoint(tmp_path / "mp", "add")
    assert_geodataframe_equal(mp, local)


def test_checkpoint_after_non_partitionable_phase_under_localmp(tmp_path):
    only = [steps()[0], Step("even", keep_even, {}, False, True), steps()[2]]
    result = LocalMultiprocess({"by": ["zone"]}).execute(
        (load, {}), only, None, {"checkpoint_dir": str(tmp_path)}
    )
    assert read_checkpoint(tmp_path, "even")["id"].tolist() == [2, 4, 6, 8, 10]
    assert result.collect()["id"].tolist() == [12, 14, 16, 18, 20]  # still runs on afterwards


def run_cli(tmp_path, monkeypatch, config_edit):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    config = yaml.safe_load((tmp_path / "plumber.yaml").read_text())
    config_edit(config)
    (tmp_path / "plumber.yaml").write_text(yaml.safe_dump(config))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    main(["run"])


def test_default_dir_is_dot_plumber_checkpoints(tmp_path, monkeypatch):
    def edit(config):
        config["phases"][0]["name"] = "scale"
        config["phases"][0]["checkpoint"] = True

    run_cli(tmp_path, monkeypatch, edit)
    assert (tmp_path / ".plumber" / "checkpoints" / "scale.parquet").exists()


def test_checkpoints_dir_setting_is_used(tmp_path, monkeypatch):
    def edit(config):
        config["checkpoints"] = {"dir": "cp"}
        config["phases"][0]["name"] = "scale"
        config["phases"][0]["checkpoint"] = True

    run_cli(tmp_path, monkeypatch, edit)
    assert (tmp_path / "cp" / "scale.parquet").exists()
