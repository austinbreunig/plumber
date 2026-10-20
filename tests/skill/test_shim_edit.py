import json
import subprocess
import sys

import pytest

from conftest import SKILL_SCRIPTS, load_helper

render_shim = load_helper("render_shim")
shim_edit = load_helper("shim_edit")

SPEC = {"name": "predict_shim", "wraps": "models:predict", "data_arg": "frame"}
NEW_SPEC = {**SPEC, "wraps": "models:predict_v2"}


@pytest.fixture
def made(tmp_path):
    render_shim.create_shim(tmp_path, SPEC)
    return tmp_path


def shim_file(repo):
    return repo / ".plumber" / "predict_shim.py"


def test_status_of_fresh_shim(made):
    status = shim_edit.shim_status(made, "predict_shim")
    assert status["skill_made"] and not status["hand_edited"]


def test_status_flags_hand_edit(made):
    shim_file(made).write_text(shim_file(made).read_text() + "# mine\n")
    assert shim_edit.shim_status(made, "predict_shim")["hand_edited"]


def test_status_hand_written_file_is_not_skill_made(tmp_path):
    (tmp_path / ".plumber").mkdir()
    (tmp_path / ".plumber" / "mine.py").write_text("def run(data):\n    return data\n")
    assert not shim_edit.shim_status(tmp_path, "mine")["skill_made"]


def test_status_missing(tmp_path):
    assert not shim_edit.shim_status(tmp_path, "nope")["exists"]


def test_edit_diff_shows_only_changes(made):
    diff = shim_edit.edit_diff(made, NEW_SPEC)
    assert "+# shim wraps models:predict_v2" in diff
    assert "-# shim wraps models:predict\n" in diff
    assert shim_edit.edit_diff(made, SPEC) == ""


def test_apply_edit_rewrites_clean_shim(made):
    assert shim_edit.apply_edit(made, NEW_SPEC)["status"] == "written"
    assert "# shim wraps models:predict_v2" in shim_file(made).read_text()
    assert shim_edit.shim_status(made, "predict_shim")["hand_edited"] is False


def test_apply_edit_hand_edited_needs_overwrite(made):
    edited = shim_file(made).read_text() + "# mine\n"
    shim_file(made).write_text(edited)
    for choice in (None, "keep", "stop"):
        assert shim_edit.apply_edit(made, NEW_SPEC, choice)["status"] == "kept"
        assert shim_file(made).read_text() == edited
    assert shim_edit.apply_edit(made, NEW_SPEC, "overwrite")["status"] == "written"
    assert "predict_v2" in shim_file(made).read_text()


def test_apply_edit_never_touches_hand_written_file(tmp_path):
    (tmp_path / ".plumber").mkdir()
    path = tmp_path / ".plumber" / "predict_shim.py"
    path.write_text("def run(data):\n    return data\n")
    result = shim_edit.apply_edit(tmp_path, NEW_SPEC, "overwrite")
    assert result["status"] == "not_skill_made"
    assert path.read_text() == "def run(data):\n    return data\n"


def test_apply_edit_missing_shim(tmp_path):
    assert shim_edit.apply_edit(tmp_path, NEW_SPEC)["status"] == "missing"


def test_remove_deletes_skill_shim(made):
    assert shim_edit.remove_shim(made, "predict_shim")["status"] == "removed"
    assert not shim_file(made).exists()


def test_remove_never_deletes_hand_written_file(tmp_path):
    (tmp_path / ".plumber").mkdir()
    path = tmp_path / ".plumber" / "mine.py"
    path.write_text("x = 1\n")
    assert shim_edit.remove_shim(tmp_path, "mine")["status"] == "not_skill_made"
    assert path.exists()


def test_remove_rejects_path_names(made):
    (made / "secret.py").write_text("# shim wraps a:b\n")
    with pytest.raises(ValueError):
        shim_edit.remove_shim(made, "../secret")
    assert (made / "secret.py").exists()


def test_remove_hand_edited_needs_overwrite(made):
    shim_file(made).write_text(shim_file(made).read_text() + "# mine\n")
    assert shim_edit.remove_shim(made, "predict_shim")["status"] == "hand_edited"
    assert shim_file(made).exists()
    assert shim_edit.remove_shim(made, "predict_shim", "overwrite")["status"] == "removed"


def test_remove_reports_phase_still_using_shim(made):
    (made / "plumber.yaml").write_text(
        "phases:\n  - path: predict_shim:run\n    name: score\n  - path: other:fn\n"
    )
    (made / "plumber.draft.yaml").write_text("phases:\n  - path: predict_shim:run\n")
    result = shim_edit.remove_shim(made, "predict_shim")
    assert result["status"] == "in_use"
    assert result["used_by"] == ["plumber.draft.yaml", "plumber.yaml"]
    assert shim_file(made).exists()


def test_used_by_ignores_similar_names(made):
    (made / "plumber.yaml").write_text("phases:\n  - path: my_predict_shim:run\n")
    assert shim_edit.used_by(made, "predict_shim") == []


def test_remove_after_repoint_succeeds(made):
    (made / "plumber.yaml").write_text("phases:\n  - path: other:fn\n")
    assert shim_edit.remove_shim(made, "predict_shim")["status"] == "removed"


def run_cli(*args, stdin=""):
    out = subprocess.run(
        [sys.executable, str(SKILL_SCRIPTS / "shim_edit.py"), *map(str, args)],
        input=stdin, capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def test_cli(made):
    assert run_cli("status", made, "predict_shim")["skill_made"]
    assert "predict_v2" in run_cli("diff", made, stdin=json.dumps(NEW_SPEC))["diff"]
    assert run_cli("edit", made, "overwrite", stdin=json.dumps(NEW_SPEC))["status"] == "written"
    assert run_cli("remove", made, "predict_shim")["status"] == "removed"
