import json

import geopandas as gpd
import pytest

from conftest import load_helper

sample = load_helper("sample")

COLUMNS = {"value": "float", "name": "str", "n": "int", "ok": "bool", "when": "datetime"}


def build(**kwargs):
    spec = {"columns": COLUMNS, "geometry": "points", "crs": "EPSG:4326"}
    return sample.build_sample(**{**spec, **kwargs})


def test_same_seed_same_rows_and_other_seed_differs():
    assert build(seed=1).equals(build(seed=1))
    assert not build(seed=1).equals(build(seed=2))


def test_default_is_20_rows_with_columns_geometry_and_crs():
    gdf = build()
    assert len(gdf) == 20
    assert list(gdf.columns) == ["value", "name", "n", "ok", "when", "geometry"]
    assert gdf.crs.to_string() == "EPSG:4326"
    assert set(gdf.geometry.geom_type) == {"Point"}


@pytest.mark.parametrize(
    "kind, expected", [("lines", "LineString"), ("polygons", "Polygon")]
)
def test_geometry_kinds(kind, expected):
    gdf = build(geometry=kind)
    assert set(gdf.geometry.geom_type) == {expected}
    assert gdf.geometry.is_valid.all()


def test_partition_fields_have_three_distinct_values():
    gdf = build(partition=["name", "n"])
    assert gdf["name"].nunique() == 3
    assert gdf["n"].nunique() == 3


def test_custom_row_count_and_too_few_rows():
    assert len(build(rows=7)) == 7
    with pytest.raises(ValueError):
        build(rows=2)


def test_unknown_type_is_an_error():
    with pytest.raises(ValueError):
        build(columns={"x": "banana"})


def test_prefill_has_partition_fields_and_param_columns():
    config = {
        "execution": {"partition": {"by": ["zone"]}},
        "phases": [{"path": "a:b", "params": {"value_col": "height", "factor": 2}}],
        "input": {"path": "m:f", "params": {"id_field": "pid", "col_x": "no"}},
    }
    assert sample.prefill_columns(config) == {"zone": "str", "height": "float", "pid": "float"}


def test_write_never_overwrites(tmp_path):
    path = tmp_path / "sub" / "s.parquet"
    gdf = build()
    sample.write_sample(path, gdf)
    with pytest.raises(FileExistsError):
        sample.write_sample(path, gdf)
    assert len(gpd.read_parquet(path)) == 20


def test_schema_has_no_row_values(tmp_path):
    path = tmp_path / "s.parquet"
    gdf = build(columns={"name": "str"}, partition=["name"])
    sample.write_sample(path, gdf)
    schema = sample.read_schema(path)
    assert schema == {
        "columns": {"name": "str"},
        "geometry": "points",
        "crs": "EPSG:4326",
        "rows": 20,
    }
    assert gdf["name"].iloc[0] not in json.dumps(schema)


def test_preview_is_five_text_rows():
    spec = sample.preview(build())
    assert len(spec["preview"]) == 5
    assert spec["rows"] == 20
    assert spec["preview"][0]["geometry"].startswith("POINT")


def test_prefill_tolerates_null_blocks():
    assert sample.prefill_columns({"execution": None, "phases": None}) == {}
    assert sample.prefill_columns({"execution": {"partition": None}}) == {}


def test_prefill_reads_plumber_yaml_when_there_is_no_draft(tmp_path):
    (tmp_path / "plumber.yaml").write_text("execution:\n  partition: {by: [zone]}\n")
    assert sample.prefill(tmp_path) == {"zone": "str"}
    (tmp_path / "plumber.draft.yaml").write_text("execution:\n  partition: {by: [county]}\n")
    assert sample.prefill(tmp_path) == {"county": "str"}
