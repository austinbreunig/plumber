import shutil
import sys
from pathlib import Path

import geopandas as gpd

from plumber.cli import main

FIXTURE = Path(__file__).parent / "fixture"


def test_plumber_run_writes_expected_output(tmp_path, monkeypatch):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))

    main(["run"])

    out = gpd.read_parquet(tmp_path / "out" / "result.parquet")
    # Worked by hand from the fixture. Zone leaders (highest value per zone):
    # A -> id 9 (3), C -> id 10 (10), B -> id 11 (17). Doubled: 6, 20, 34. Tagged > 15.
    assert out["id"].tolist() == [9, 10, 11]
    assert out["zone"].tolist() == ["A", "C", "B"]
    assert out["value"].tolist() == [6, 20, 34]
    assert out["high"].tolist() == [False, True, True]
    assert out.crs.to_string() == "EPSG:4326"
