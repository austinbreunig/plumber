import sys

from conftest import load_helper

scan = load_helper("scan_signatures")


def by_label(found):
    return {f["label"]: f for f in found}


def test_finds_fixture_functions_with_dotted_module_paths(repo):
    found = by_label(scan.scan_signatures(repo))
    assert "myio:load_fixture()" in found
    assert "myio:write_parquet(gdf, path)" in found
    assert "phases.scale_value:run(gdf, factor=1, **params)" in found
    assert found["myio:load_fixture()"]["path"] == "myio:load_fixture"


def test_reports_required_params_hints_and_first_docstring_line(repo):
    (repo / "extra.py").write_text(
        'def f(data, col: str, n: int = 3, *, mode="x", **kw) -> int:\n'
        '    """First line.\n\n    More."""\n'
    )
    f = by_label(scan.scan_signatures(repo))["extra:f(data, col: str, n: int = 3, mode='x', **kw)"]
    assert f["doc"] == "First line."
    assert f["params"] == [
        {"name": "data", "hint": None, "default": None, "required": True},
        {"name": "col", "hint": "str", "default": None, "required": True},
        {"name": "n", "hint": "int", "default": "3", "required": False},
        {"name": "mode", "hint": None, "default": "'x'", "required": False},
    ]


def test_skips_venvs_hidden_folders_tests_and_plumber_dir(repo):
    for folder in [".venv", "env", ".hidden", "tests", ".plumber", "pkg/tests"]:
        (repo / folder).mkdir(parents=True)
        (repo / folder / "bad.py").write_text("def skipped(data): pass\n")
    (repo / "env" / "pyvenv.cfg").write_text("home = /usr/bin\n")
    labels = " ".join(by_label(scan.scan_signatures(repo)))
    assert "skipped" not in labels


def test_never_imports_and_ignores_bodies_and_broken_files(repo):
    (repo / "boom.py").write_text(
        "raise RuntimeError('imported!')\n"
        "def g(data):\n    raise RuntimeError('body')\n"
        "class K:\n    def method(self): pass\n"
    )
    (repo / "broken.py").write_text("def (:\n")
    found = by_label(scan.scan_signatures(repo))
    assert "boom:g(data)" in found
    assert "method" not in " ".join(found)
    assert "boom" not in sys.modules


def test_flags_tuple_returns_from_annotation_or_docstring(repo):
    (repo / "tup.py").write_text(
        "def a(data) -> tuple[int, str]:\n    pass\n"
        'def b(data):\n    """Cluster.\n\n    Return (output_gdf, summary_dict).\n    """\n'
        "def c(data) -> int:\n    pass\n"
    )
    found = {f["name"]: f["returns_tuple"] for f in scan.scan_signatures(repo)}
    assert found["a"] and found["b"] and not found["c"]


def test_resolves_bare_name_defaults_to_module_literals(repo):
    (repo / "consts.py").write_text(
        "DEFAULT_EPSILONS = (80, 35)\nLIMIT = 3\nSTATE = make()\n"
        "def f(data, eps=DEFAULT_EPSILONS, n=LIMIT, s=STATE, m=MISSING):\n    pass\n"
    )
    f = next(f for f in scan.scan_signatures(repo) if f["name"] == "f")
    defaults = {p["name"]: p["default"] for p in f["params"]}
    assert defaults == {"data": None, "eps": "(80, 35)", "n": "3", "s": "STATE", "m": "MISSING"}
