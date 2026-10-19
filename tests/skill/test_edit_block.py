from conftest import load_helper

edit_block = load_helper("edit_block")

COMMENTED = """\
# my pipeline
input:
  path: myio:load_fixture   # loader
  params: {}

# the steps
phases:
  # scale first
  - path: phases.scale_value:run
    partitionable: true

    params: {factor: 2}

output:
  path: myio:write_parquet
  params: {path: out/result.parquet}
"""


def test_replaces_only_the_touched_block():
    new = "phases:\n  - path: phases.scale_value:run\n    partitionable: false\n    params: {factor: 3}\n"
    out = edit_block.replace_block(COMMENTED, "phases", new)
    old_lines = COMMENTED.splitlines()
    out_lines = out.splitlines()
    assert out_lines[:6] == old_lines[:6]  # input block, blank, comment: byte-for-byte
    assert out_lines[6:10] == new.splitlines()
    assert out_lines[10:] == old_lines[-4:]  # blank line, then the output block
    assert "# my pipeline" in out and "# the steps" in out


def test_block_stops_before_next_keys_comment_and_blank_lines():
    out = edit_block.replace_block(COMMENTED, "input", "input:\n  path: a:b\n")
    assert out.startswith("# my pipeline\ninput:\n  path: a:b\n\n# the steps\nphases:")


def test_key_order_is_kept_and_other_keys_are_not_matched_by_prefix():
    text = "inputs: 1\ninput:\n  path: a:b\nuser_level: 2\n"
    assert edit_block.replace_block(text, "input", "input:\n  path: c:d\n") == (
        "inputs: 1\ninput:\n  path: c:d\nuser_level: 2\n"
    )


def test_block_with_column_zero_list_items():
    text = "phases:\n- path: a:b\n- path: c:d\nuser_level: 2\n"
    assert edit_block.replace_block(text, "phases", "phases: []\n") == "phases: []\nuser_level: 2\n"


def test_missing_key_is_appended_at_the_end():
    out = edit_block.replace_block("input:\n  path: a:b", "user_level", "user_level: 2\n")
    assert out == "input:\n  path: a:b\nuser_level: 2\n"


def test_new_block_without_trailing_newline_is_fine():
    assert edit_block.replace_block("a: 1\nb: 2\n", "a", "a: 9") == "a: 9\nb: 2\n"


def test_edit_draft_copies_config_keeps_base_and_validates(repo):
    before = (repo / "plumber.yaml").read_text()
    result = edit_block.edit_draft(repo, "phases", (
        "phases:\n  - path: phases.scale_value:run\n    partitionable: false\n"
        "    params: {factor: 5}\n"
    ))
    assert result["error"] is None
    assert (repo / "plumber.yaml").read_text() == before  # original untouched
    draft = (repo / "plumber.draft.yaml").read_text().splitlines()
    assert draft[0].startswith("# base: ") and draft[0] != "# base: none"
    assert "factor: 5" in "\n".join(draft)
    assert "output:\n  path: myio:write_parquet" in "\n".join(draft)


def test_edit_draft_reports_a_draft_that_does_not_load(repo):
    result = edit_block.edit_draft(repo, "phases", "phases: [\n")
    assert result["error"]
    assert (repo / "plumber.draft.yaml").exists()  # still saved, so nothing is lost


def test_edit_draft_edits_the_existing_draft_not_the_config(repo):
    edit_block.edit_draft(repo, "input", "input:\n  path: myio:load_fixture\n  params: {n: 1}\n")
    edit_block.edit_draft(repo, "output", "output:\n  path: myio:write_parquet\n  params: {}\n")
    draft = (repo / "plumber.draft.yaml").read_text()
    assert "params: {n: 1}" in draft and "params: {}" in draft
    assert draft.count("# base:") == 1
