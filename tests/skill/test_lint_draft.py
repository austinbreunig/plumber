from conftest import load_helper

detect_case = load_helper("detect_case")
lint_draft = load_helper("lint_draft")


def write(repo, text):
    path = repo / "plumber.draft.yaml"
    path.write_text(text)
    return path


PHASES = """\
phases:
  - path: phases.scale_value:run
    partitionable: {first}
    params: {{factor: 2}}
  - path: phases.scale_value:run
    {name}partitionable: {second}
    params: {{factor: 3}}
"""


def test_duplicate_phase_names_are_reported(repo):
    path = write(repo, PHASES.format(first="true", second="true", name=""))
    result = lint_draft.lint_draft(path)
    assert any("phases.scale_value:run" in p and "1" in p and "2" in p for p in result["problems"])


def test_distinct_name_resolves_the_duplicate(repo):
    path = write(repo, PHASES.format(first="true", second="true", name="name: scale_again\n    "))
    assert lint_draft.lint_draft(path)["problems"] == []


def test_localmp_with_no_partitionable_phase_warns(repo):
    text = PHASES.format(first="false", second="false", name="name: b\n    ")
    path = write(repo, text + "execution:\n  strategy: localmp\n  partition: {worker_count: 2}\n")
    result = lint_draft.lint_draft(path)
    assert result["problems"] == []
    assert any("localmp" in w and "partitionable" in w for w in result["warnings"])


def test_localmp_needs_exactly_one_partition_key(repo):
    text = PHASES.format(first="true", second="true", name="name: b\n    ")
    path = write(
        repo, text + "execution:\n  strategy: localmp\n  partition: {by: [a], worker_count: 2}\n"
    )
    assert any("exactly one" in p for p in lint_draft.lint_draft(path)["problems"])


def test_missing_output_repeats_the_discard_warning(repo):
    path = write(repo, "phases:\n  - path: phases.scale_value:run\n    partitionable: true\n")
    assert any("result discarded" in w for w in lint_draft.lint_draft(path)["warnings"])


def test_fixture_pipeline_with_full_tail_passes_check(repo):
    path = write(
        repo,
        (repo / "plumber.yaml").read_text()
        + "execution:\n  strategy: localmp\n  partition: {chunk_size: 5}\n"
        "checkpoints: {dir: .plumber/checkpoints}\nuser_level: INFO\n",
    )
    assert lint_draft.lint_draft(path) == {"problems": [], "warnings": []}
    assert detect_case.check_findings(path) == []
