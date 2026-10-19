from conftest import load_helper

find_venv = load_helper("find_venv")


def make_venv(path, version=None):
    """A fake venv. `version` is what its python prints; None means plumber is not installed."""
    (path / "bin").mkdir(parents=True)
    (path / "pyvenv.cfg").write_text("home = /usr/bin\n")
    python = path / "bin" / "python"
    body = f"echo {version}" if version else "exit 1"
    python.write_text(f"#!/bin/sh\n{body}\n")
    python.chmod(0o755)
    return path


def test_version_at_least_compares_numbers_not_text():
    assert find_venv.version_at_least("0.1.2", "0.1.2")
    assert find_venv.version_at_least("0.10.0", "0.2.0")
    assert not find_venv.version_at_least("0.1.1", "0.1.2")


def test_find_venvs_finds_any_pyvenv_cfg(tmp_path):
    make_venv(tmp_path / ".venv")
    make_venv(tmp_path / "tools" / "env")
    (tmp_path / "src").mkdir()
    found = find_venv.find_venvs(tmp_path)
    assert sorted(found) == [tmp_path / ".venv", tmp_path / "tools" / "env"]


def test_plumber_version_reads_the_venv_python(tmp_path):
    assert find_venv.plumber_version(make_venv(tmp_path / "a", "0.1.5")) == "0.1.5"
    assert find_venv.plumber_version(make_venv(tmp_path / "b")) is None


def test_one_working_venv_is_chosen(tmp_path):
    good = make_venv(tmp_path / ".venv", "0.1.2")
    make_venv(tmp_path / "other")  # no plumber
    result = find_venv.pick_venv(tmp_path, virtual_env=None)
    assert result["status"] == "ok"
    assert result["venv"] == str(good)


def test_active_venv_wins_over_others(tmp_path):
    make_venv(tmp_path / "a", "0.1.2")
    active = make_venv(tmp_path / "b", "0.1.2")
    result = find_venv.pick_venv(tmp_path, virtual_env=str(active))
    assert result["status"] == "ok"
    assert result["venv"] == str(active)


def test_several_working_venvs_means_ask(tmp_path):
    a = make_venv(tmp_path / "a", "0.1.2")
    b = make_venv(tmp_path / "b", "0.1.3")
    result = find_venv.pick_venv(tmp_path, virtual_env=None)
    assert result["status"] == "ask"
    assert sorted(result["candidates"]) == [str(a), str(b)]


def test_active_venv_outside_the_repo_is_ignored(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    mine = make_venv(repo / ".venv", "0.1.2")
    elsewhere = make_venv(tmp_path / "elsewhere", "0.1.2")
    result = find_venv.pick_venv(repo, virtual_env=str(elsewhere))
    assert result["venv"] == str(mine)


def test_no_venv_stops_with_the_fix_command(tmp_path):
    result = find_venv.pick_venv(tmp_path, virtual_env=None)
    assert result["status"] == "stop"
    assert "uv" in result["fix"]


def test_plumber_missing_stops_with_install_command(tmp_path):
    make_venv(tmp_path / ".venv")
    result = find_venv.pick_venv(tmp_path, virtual_env=None)
    assert result["status"] == "stop"
    assert result["fix"] == "uv add ab-plumber"


def test_plumber_too_old_stops_with_upgrade_command(tmp_path):
    make_venv(tmp_path / ".venv", "0.0.9")
    result = find_venv.pick_venv(tmp_path, virtual_env=None)
    assert result["status"] == "stop"
    assert find_venv.MIN_PLUMBER_VERSION in result["fix"]
    assert "0.0.9" in result["reason"]

