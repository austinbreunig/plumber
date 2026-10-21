import json
import subprocess
import sys

import pytest

from conftest import SKILL_SCRIPTS, load_helper

base_hash = load_helper("base_hash")
render_shim = load_helper("render_shim")

SPEC = {
    "name": "predict_shim",
    "wraps": "models:predict",
    "data_arg": "frame",
    "loaders": [{"param": "model", "loader": "models:load_model", "source": "model_source"}],
    "passthrough": ["threshold"],
}


def test_render_has_base_then_wraps_lines():
    lines = render_shim.render_shim(SPEC).splitlines()
    assert lines[0].startswith("# base: ")
    assert lines[1] == "# shim wraps models:predict"


def test_base_line_matches_text():
    text = render_shim.render_shim(SPEC)
    assert base_hash.read_base(text) == base_hash.hash_text(text)


def test_render_runs_and_wires_arguments(tmp_path, monkeypatch):
    (tmp_path / "models.py").write_text(
        "def load_model(path):\n    return 'M:' + path\n"
        "def predict(frame, model, threshold):\n    return (frame, model, threshold)\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    ns = {}
    exec(render_shim.render_shim(SPEC), ns)
    assert ns["run"]("d", model_source="m.bin", threshold=5) == ("d", "M:m.bin", 5)


def test_create_writes_file_in_dot_plumber(tmp_path):
    path = render_shim.create_shim(tmp_path, SPEC)
    assert path == tmp_path / ".plumber" / "predict_shim.py"
    assert base_hash.base_matches(path)


def test_create_never_overwrites(tmp_path):
    render_shim.create_shim(tmp_path, SPEC)
    target = tmp_path / ".plumber" / "predict_shim.py"
    target.write_text("mine")
    with pytest.raises(FileExistsError):
        render_shim.create_shim(tmp_path, SPEC)
    assert target.read_text() == "mine"


def test_name_taken(tmp_path):
    assert not render_shim.name_taken(tmp_path, "predict_shim")
    render_shim.create_shim(tmp_path, SPEC)
    assert render_shim.name_taken(tmp_path, "predict_shim")


def test_no_loaders_no_passthrough():
    text = render_shim.render_shim({"name": "s", "wraps": "a.b:f", "data_arg": "data"})
    ns = {}
    exec(text.replace("from a.b import f as _wrapped", "_wrapped = lambda data: data"), ns)
    assert ns["run"](3) == 3


def test_bad_names_rejected():
    with pytest.raises(ValueError):
        render_shim.render_shim({**SPEC, "name": "../evil"})
    with pytest.raises(ValueError):
        render_shim.render_shim({**SPEC, "wraps": "models"})


def test_loader_needs_exactly_one_required_param():
    one = [{"name": "p", "required": True}, {"name": "q", "required": False}]
    assert render_shim.loader_ok(one)
    assert not render_shim.loader_ok([])
    assert not render_shim.loader_ok([{"name": "a", "required": True}] * 2)
    assert not render_shim.loader_ok([{"name": "a", "required": False}])


def test_main_prints_json(tmp_path):
    out = subprocess.run(
        [sys.executable, str(SKILL_SCRIPTS / "render_shim.py"), "create", str(tmp_path)],
        input=json.dumps(SPEC), capture_output=True, text=True, check=True,
    ).stdout
    assert json.loads(out)["path"].endswith("predict_shim.py")


@pytest.mark.parametrize("name", ["models", "mod"])
def test_shim_name_cannot_shadow_a_wrapped_module(name):
    spec = {**SPEC, "name": name, "loaders": [{**SPEC["loaders"][0], "loader": "mod:load"}]}
    with pytest.raises(ValueError):
        render_shim.render_shim(spec)


def run_shim(tmp_path, monkeypatch, spec):
    (tmp_path / "clusters.py").write_text(
        "def cluster(frame, n):\n    return (frame + n, 'summary')\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    ns = {}
    exec(render_shim.render_shim(spec), ns)
    return ns["run"]


TUPLE_SPEC = {
    "name": "cluster_shim",
    "wraps": "clusters:cluster",
    "data_arg": "frame",
    "passthrough": ["n"],
}


def test_result_index_returns_only_that_item(tmp_path, monkeypatch):
    run = run_shim(tmp_path, monkeypatch, {**TUPLE_SPEC, "result_index": 0})
    assert run(1, n=2) == 3


def test_no_result_index_leaves_the_return_untouched(tmp_path, monkeypatch):
    run = run_shim(tmp_path, monkeypatch, TUPLE_SPEC)
    assert run(1, n=2) == (3, "summary")
    assert "[" not in render_shim.render_shim(TUPLE_SPEC).split("def run")[1]


@pytest.mark.parametrize("bad", [-1, "0", 1.5, True])
def test_bad_result_index_raises(bad):
    with pytest.raises(ValueError, match="result_index"):
        render_shim.render_shim({**TUPLE_SPEC, "result_index": bad})
