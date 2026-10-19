import subprocess

from conftest import load_helper

exclude = load_helper("exclude_append")


def init_git(repo):
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo / ".git" / "info" / "exclude"


def test_appends_lines_and_never_touches_gitignore(repo):
    path = init_git(repo)
    result = exclude.exclude_append(repo, ["plumber.yaml", ".plumber/"])
    assert result["status"] == "ok"
    assert result["added"] == ["plumber.yaml", ".plumber/"]
    assert path.read_text().splitlines()[-2:] == ["plumber.yaml", ".plumber/"]
    assert not (repo / ".gitignore").exists()


def test_keeps_existing_content_and_skips_duplicates(repo):
    path = init_git(repo)
    before = path.read_text()
    path.write_text(before + "plumber.yaml")  # no trailing newline on purpose
    result = exclude.exclude_append(repo, ["plumber.yaml", "plumber.draft.yaml"])
    assert result["added"] == ["plumber.draft.yaml"]
    assert result["skipped"] == ["plumber.yaml"]
    assert path.read_text() == before + "plumber.yaml\nplumber.draft.yaml\n"


def test_running_twice_adds_nothing(repo):
    init_git(repo)
    exclude.exclude_append(repo, [".plumber/"])
    assert exclude.exclude_append(repo, [".plumber/"])["added"] == []


def test_outside_a_git_repo_is_skipped(repo):
    result = exclude.exclude_append(repo, ["plumber.yaml"])
    assert result["status"] == "skipped"
