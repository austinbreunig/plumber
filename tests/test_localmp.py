import shutil
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
import yaml

from plumber.cli import main
from plumber.localmp import LocalMultiprocess, join, split
from plumber.protocols import Step

FIXTURE = Path(__file__).parent / "fixture"


def frame(n=10):
    return pd.DataFrame({"id": range(n), "zone": ["a", "b"] * (n // 2)})


def test_split_by_makes_one_piece_per_value():
    pieces = split(frame(), {"by": ["zone"]})
    assert [sorted(p["zone"].unique()) for p in pieces] == [["a"], ["b"]]


def test_split_chunk_size_slices_in_order():
    pieces = split(frame(10), {"chunk_size": 4})
    assert [p["id"].tolist() for p in pieces] == [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]]


def test_split_worker_count_gives_roughly_equal_slices():
    pieces = split(frame(10), {"worker_count": 3})
    assert [len(p) for p in pieces] == [4, 3, 3]


def test_join_restores_input_row_order():
    data = frame()
    pieces = split(data, {"by": ["zone"]})  # a-rows first, then b-rows
    joined = join(pieces, data.index)
    assert joined["id"].tolist() == list(range(10))
    assert list(joined.columns) == ["id", "zone"]


def test_split_by_keeps_rows_with_null_keys():
    data = pd.DataFrame({"id": range(4), "zone": ["a", None, "a", None]})
    pieces = split(data, {"by": ["zone"]})
    assert sum(len(p) for p in pieces) == 4


# Phases for the strategy tests. Module level so worker processes can pickle them.
def add(data, amount):
    data = data.copy()
    data["id"] = data["id"] + amount
    return data


def keep_first(data):
    return data.head(1)


def seen_columns(data):
    assert list(data.columns) == ["id", "zone"]  # no helper column leaks into phases
    return data


def rebuild_without_zone(data):
    return data[["id"]].copy()


def test_phases_never_see_a_helper_column():
    steps = [Step("seen", seen_columns, {}, True, False)]
    result = LocalMultiprocess({"chunk_size": 3}).execute((frame, {}), steps, None, {})
    assert list(result.collect().columns) == ["id", "zone"]


def test_phase_that_drops_columns_keeps_row_order():
    steps = [Step("drop", rebuild_without_zone, {}, True, False)]
    result = LocalMultiprocess({"by": ["zone"]}).execute((frame, {}), steps, None, {})
    assert result.collect()["id"].tolist() == list(range(10))


def test_non_partitionable_phase_sees_all_rows_once():
    steps = [
        Step("add", add, {"amount": 100}, True, False),
        Step("first", keep_first, {}, False, False),
    ]
    result = LocalMultiprocess({"chunk_size": 3}).execute((frame, {}), steps, None, {})
    assert result.collect()["id"].tolist() == [100]  # one row: it ran on the joined data


def test_output_runs_once_on_joined_data():
    seen = []

    def write(data):
        seen.append(data["id"].tolist())

    steps = [Step("add", add, {"amount": 1}, True, False)]
    LocalMultiprocess({"worker_count": 2}).execute((frame, {}), steps, (write, {}), {})
    assert seen == [list(range(1, 11))]


def run_cli(tmp_path, monkeypatch, out, *flags):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    config = yaml.safe_load((tmp_path / "plumber.yaml").read_text())
    config["output"]["params"]["path"] = out
    (tmp_path / "plumber.yaml").write_text(yaml.safe_dump(config))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    main(["run", *flags])
    return gpd.read_parquet(tmp_path / out)


@pytest.mark.parametrize(
    "flags",
    [["--by", "zone"], ["--chunk-size", "5"], ["--worker-count", "3"]],
)
def test_localmp_matches_local_on_tracer_fixture(tmp_path, monkeypatch, flags):
    expected = run_cli(tmp_path, monkeypatch, "out/local.parquet")
    actual = run_cli(tmp_path, monkeypatch, "out/mp.parquet", "--strategy", "localmp", *flags)
    pd.testing.assert_frame_equal(pd.DataFrame(actual), pd.DataFrame(expected))
    assert actual.crs == expected.crs


def test_cli_partition_flags_replace_config_partition(tmp_path, monkeypatch):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    config = yaml.safe_load((tmp_path / "plumber.yaml").read_text())
    config["execution"] = {"strategy": "localmp", "partition": {"by": ["zone"]}}
    (tmp_path / "plumber.yaml").write_text(yaml.safe_dump(config))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    main(["run", "--worker-count", "2"])  # would fail check if both keys were kept
    assert (tmp_path / "out" / "result.parquet").exists()
