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


def test_rewrite_keeps_the_existing_base_line(repo):
    write_draft.write_draft(repo, "a: 1\n")
    first = (repo / "plumber.draft.yaml").read_text().splitlines()[0]
    (repo / "plumber.yaml").write_text((repo / "plumber.yaml").read_text() + "\n# edited\n")
    path = write_draft.write_draft(repo, "a: 2\n")
    assert path.read_text() == f"{first}\na: 2\n"


def test_rebase_restamps_from_the_current_config(repo):
    write_draft.write_draft(repo, "a: 1\n")
    (repo / "plumber.yaml").write_text((repo / "plumber.yaml").read_text() + "\n# edited\n")
    path = write_draft.write_draft(repo, "a: 2\n", rebase=True)
    assert path.read_text().splitlines()[0] == "# base: " + base_hash.hash_file(
        repo / "plumber.yaml"
    )


def test_edit_block_keeps_base_and_drift_still_shows(repo):
    detect_case = load_helper("detect_case")
    edit_block = load_helper("edit_block")
    edit_block.edit_draft(repo, "output", "output:\n  path: myio:write_parquet\n")
    (repo / "plumber.yaml").write_text((repo / "plumber.yaml").read_text() + "\n# edited\n")
    edit_block.edit_draft(repo, "output", "output:\n  path: myio:write_parquet\n  params: {}\n")
    assert detect_case.has_drifted(repo) is True
