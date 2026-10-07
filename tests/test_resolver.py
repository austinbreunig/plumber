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
