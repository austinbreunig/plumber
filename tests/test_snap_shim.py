import shutil
import sys
from pathlib import Path

import geopandas as gpd
import pytest
import yaml
from shapely.geometry import LineString

from plumber.check import check
from plumber.cli import main

FIXTURE = Path(__file__).parent / "fixture"


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Fixture project plus a network file and a config that uses the example shim."""
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    # One road along y=0 from x=0 to x=11.
    network = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (11, 0)])], crs="EPSG:4326")
    network.to_parquet("network.parquet")
    config = {
        "input": {"path": "myio:load_fixture"},
        "phases": [
            {
                "path": "plumber.examples.snap_shim:run",
                "partitionable": True,
                "params": {"network_path": "network.parquet", "tolerance": 2.0},
            }
        ],
        "output": {"path": "myio:write_parquet", "params": {"path": "out/snapped.parquet"}},
    }
    Path("plumber.yaml").write_text(yaml.safe_dump(config))
    return tmp_path


def test_check_passes_for_the_shim(project):
    config = yaml.safe_load(Path("plumber.yaml").read_text())
    assert check(config)["ok"] is True


def test_run_snaps_close_points_and_leaves_far_ones(project):
    main(["run"])

    out = gpd.read_parquet("out/snapped.parquet")
    # The fixture has points (i, i) for i in 0..11. The road is y=0, tolerance 2.
    # Points 0, 1, 2 are within 2 of the road: they land on (i, 0). The rest stay put.
    assert [(p.x, p.y) for p in out.geometry[:4]] == [(0, 0), (1, 0), (2, 0), (3, 3)]
    assert len(out) == 12
