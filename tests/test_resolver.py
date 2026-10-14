import sys

import pytest

from plumber.resolver import resolve


def test_resolves_module_attr_to_callable():
    assert resolve("os.path:join").__name__ == "join"


def test_path_without_attr_is_an_error():
    with pytest.raises(ValueError, match="module:attr"):
        resolve("os.path")


def test_current_folder_is_importable(tmp_path, monkeypatch):
    (tmp_path / "mymod_for_resolver_test.py").write_text("def hello():\n    return 'hi'\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert resolve("mymod_for_resolver_test:hello")() == "hi"


def test_plumber_folder_is_importable(tmp_path, monkeypatch):
    (tmp_path / ".plumber").mkdir()
    module = tmp_path / ".plumber" / "mymod_in_plumber_dir.py"
    module.write_text("def hello():\n    return 'hi'\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert resolve("mymod_in_plumber_dir:hello")() == "hi"


def test_plumber_folder_wins_over_current_folder(tmp_path, monkeypatch):
    (tmp_path / ".plumber").mkdir()
    (tmp_path / "mymod_in_both.py").write_text("def who():\n    return 'project'\n")
    (tmp_path / ".plumber" / "mymod_in_both.py").write_text("def who():\n    return 'plumber'\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delitem(sys.modules, "mymod_in_both", raising=False)
    assert resolve("mymod_in_both:who")() == "plumber"
