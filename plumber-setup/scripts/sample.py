"""Build a check sample and read a sample's schema. Run with the target repo's venv Python.

  <venv>/bin/python sample.py prefill [repo]   reads the draft, else plumber.yaml
                                               -> {"columns": {name: type}}
  <venv>/bin/python sample.py schema <file>    -> {"columns", "geometry", "crs", "rows"}
                                               Reads the file's metadata only, never row values.
  <venv>/bin/python sample.py preview < spec   -> {"rows", "columns", "preview": [5 rows as text]}
  <venv>/bin/python sample.py write < spec     -> same, and writes spec["path"]. Never overwrites:
                                               {"status": "exists", "path": ...} if it exists.
spec (JSON on stdin): {"path", "columns": {name: type}, "geometry": "points|lines|polygons",
  "crs": "EPSG:4326", "rows": 20, "seed": 0, "partition": [column, ...]}
Types: int, float, str, bool, datetime.
"""

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import geopandas as gpd
import pyarrow.parquet as pq
import yaml
from pyproj import CRS
from shapely.geometry import LineString, Point, Polygon

sys.path.insert(0, str(Path(__file__).parent))

from common import CONFIG, DRAFT  # noqa: E402

TYPES = ("int", "float", "str", "bool", "datetime")
PARTITION_VALUES = 3
PREVIEW_ROWS = 5
PARAM_SUFFIXES = ("_col", "_column", "_field")
KIND_OF = {"Point": "points", "LineString": "lines", "Polygon": "polygons"}


def prefill_columns(config):
    """Columns the config already implies: partition fields and `*_col/_column/_field` params."""
    columns = {}
    partition = (config.get("execution") or {}).get("partition") or {}
    for name in partition.get("by") or []:
        columns[name] = "str"
    entries = [config.get("input"), config.get("output"), *(config.get("phases") or [])]
    for entry in entries:
        for key, value in ((entry or {}).get("params") or {}).items():
            if key.endswith(PARAM_SUFFIXES) and isinstance(value, str):
                columns.setdefault(value, "float")
    return columns


def prefill(repo):
    """Prefill columns from the draft, else plumber.yaml (the draft is gone after approve)."""
    repo = Path(repo)
    path = repo / DRAFT if (repo / DRAFT).exists() else repo / CONFIG
    return prefill_columns(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def make_value(kind, row, rng, cycle):
    """One cell. `cycle` means a partition field: only 3 distinct values."""
    if kind not in TYPES:
        raise ValueError(f"unknown type {kind!r}; use one of {', '.join(TYPES)}")
    if cycle:
        number = row % PARTITION_VALUES
        return number if kind == "int" else f"p{number}"  # other types become text
    if kind == "int":
        return rng.randint(0, 100)
    if kind == "float":
        return round(rng.uniform(0, 100), 3)
    if kind == "bool":
        return rng.random() < 0.5
    if kind == "datetime":
        return datetime(2024, 1, 1) + timedelta(hours=rng.randint(0, 24 * 365))
    return f"s{rng.randint(0, 999)}"


def make_geometry(kind, rng, geographic):
    x, y = (rng.uniform(-1, 1) - 100, rng.uniform(-1, 1) + 40) if geographic else (
        rng.uniform(0, 1000), rng.uniform(0, 1000))
    size = 0.01 if geographic else 10
    if kind == "points":
        return Point(x, y)
    if kind == "lines":
        return LineString([(x, y), (x + size, y + size)])
    if kind == "polygons":
        return Polygon([(x, y), (x + size, y), (x + size, y + size), (x, y + size)])
    raise ValueError(f"unknown geometry {kind!r}; use points, lines or polygons")


def build_sample(columns, geometry="points", crs="EPSG:4326", rows=20, seed=0, partition=()):
    """A seeded GeoDataFrame. Same arguments, same rows."""
    if rows < PARTITION_VALUES:
        raise ValueError(f"rows must be at least {PARTITION_VALUES}")
    rng = random.Random(seed)
    geographic = CRS.from_user_input(crs).is_geographic
    data = {
        name: [make_value(kind, row, rng, name in partition) for row in range(rows)]
        for name, kind in columns.items()
    }
    shapes = [make_geometry(geometry, rng, geographic) for _ in range(rows)]
    return gpd.GeoDataFrame(data, geometry=shapes, crs=crs)


def write_sample(path, gdf):
    path = Path(path)
    if path.exists():
        raise FileExistsError(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(path)


def type_name(arrow_type):
    text = str(arrow_type)
    if text.startswith("int"):
        return "int"
    if text.startswith(("float", "double")):
        return "float"
    if text.startswith("bool"):
        return "bool"
    if text.startswith("timestamp"):
        return "datetime"
    return "str"


def read_schema(path):
    """Columns, types, geometry kind, CRS and row count. Metadata only: no row is read."""
    parquet = pq.ParquetFile(path)
    geo = json.loads(parquet.schema_arrow.metadata[b"geo"])
    main = geo["columns"][geo["primary_column"]]
    kinds = {KIND_OF.get(t.split()[0], t) for t in main.get("geometry_types", [])}
    crs = CRS.from_json_dict(main["crs"]).to_string() if main.get("crs") else None
    columns = {
        field.name: type_name(field.type)
        for field in parquet.schema_arrow
        if field.name != geo["primary_column"]
    }
    return {
        "columns": columns,
        "geometry": kinds.pop() if len(kinds) == 1 else sorted(kinds),
        "crs": crs,
        "rows": parquet.metadata.num_rows,
    }


def preview(gdf):
    text = gdf.head(PREVIEW_ROWS).astype(str)
    return {
        "rows": len(gdf),
        "columns": {name: str(dtype) for name, dtype in gdf.dtypes.items()},
        "crs": str(gdf.crs),
        "preview": text.to_dict("records"),
    }


def from_spec(spec):
    return build_sample(
        spec["columns"], spec.get("geometry", "points"), spec.get("crs", "EPSG:4326"),
        spec.get("rows", 20), spec.get("seed", 0), spec.get("partition", ()),
    )


def main():
    command = sys.argv[1]
    if command == "prefill":
        repo = Path(sys.argv[2] if len(sys.argv) > 2 else ".")
        result = {"columns": prefill(repo)}
    elif command == "schema":
        result = read_schema(sys.argv[2])
    else:
        spec = json.load(sys.stdin)
        gdf = from_spec(spec)
        result = preview(gdf)
        result["path"] = spec["path"]
        if command == "write":
            try:
                write_sample(spec["path"], gdf)
            except FileExistsError:
                result = {"status": "exists", "path": spec["path"]}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
