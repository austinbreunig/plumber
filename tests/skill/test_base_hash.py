from conftest import load_helper

base_hash = load_helper("base_hash")


def test_same_text_same_hash_and_edit_changes_it():
    assert base_hash.hash_text("a: 1\n") == base_hash.hash_text("a: 1\n")
    assert base_hash.hash_text("a: 1\n") != base_hash.hash_text("a: 2\n")


def test_base_line_is_ignored_when_hashing():
    assert base_hash.hash_text("# base: abc\na: 1\n") == base_hash.hash_text("a: 1\n")


def test_hash_file_is_none_when_missing(tmp_path):
    assert base_hash.hash_file(tmp_path / "nope.yaml") == "none"


def test_hash_file_matches_hash_text(tmp_path):
    (tmp_path / "plumber.yaml").write_text("a: 1\n")
    assert base_hash.hash_file(tmp_path / "plumber.yaml") == base_hash.hash_text("a: 1\n")


def test_read_base():
    assert base_hash.read_base("# base: abc123\nx: 1\n") == "abc123"
    assert base_hash.read_base("x: 1\n") is None


def test_hand_edit_is_caught(tmp_path):
    shim = tmp_path / "s.py"
    body = "def run(data): pass\n"
    shim.write_text(f"# base: {base_hash.hash_text(body)}\n{body}")
    assert base_hash.base_matches(shim)
    shim.write_text(shim.read_text() + "# my edit\n")
    assert not base_hash.base_matches(shim)
