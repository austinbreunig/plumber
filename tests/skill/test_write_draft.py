from conftest import load_helper

base_hash = load_helper("base_hash")
write_draft = load_helper("write_draft")


def test_case_a_draft_starts_with_base_none(repo):
    (repo / "plumber.yaml").unlink()
    path = write_draft.write_draft(repo, "phases: []\n")
    lines = path.read_text().splitlines()
    assert path.name == "plumber.draft.yaml"
    assert lines[0] == "# base: none"
    assert lines[1] == "phases: []"


def test_draft_records_hash_of_existing_config(repo):
    path = write_draft.write_draft(repo, "phases: []\n")
    first = path.read_text().splitlines()[0]
    assert first == "# base: " + base_hash.hash_file(repo / "plumber.yaml")


def test_rewrite_replaces_and_does_not_stack_base_lines(repo):
    (repo / "plumber.yaml").unlink()
    write_draft.write_draft(repo, "a: 1\n")
    path = write_draft.write_draft(repo, "# base: none\na: 2\n")
    assert path.read_text() == "# base: none\na: 2\n"
