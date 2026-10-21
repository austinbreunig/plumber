from conftest import load_helper

recommend = load_helper("recommend")


def row(label, status, *messages):
    return {"label": label, "name": label, "status": status, "messages": list(messages)}


def only(rows):
    return recommend.recommend({"rows": rows})["items"]


# ---- classify: offer what the skill owns, tell the rest ----


def test_partitionable_fail_is_an_offer_to_set_false():
    item = recommend.classify("P1", "FAIL", "different output on identical input (shared state?)")
    assert item["kind"] == "offer"
    assert item["action"] == "set_partitionable_false"


def test_crash_is_tell_only():
    item = recommend.classify("P2", "FAIL", "KeyError: 'value'")
    assert (item["kind"], item["action"]) == ("tell", "crash")


def test_crs_change_is_tell_only_and_a_question():
    item = recommend.classify("P1", "WARN", "CRS changed from EPSG:4326 to EPSG:3857")
    assert (item["kind"], item["action"]) == ("tell", "crs_changed")
    assert item["text"].endswith("?")


def test_dropped_columns_are_tell_only_and_ask_intended():
    item = recommend.classify("P1", "WARN", "columns dropped: value, zone")
    assert (item["kind"], item["action"]) == ("tell", "dropped_columns")
    assert item["columns"] == ["value", "zone"]
    assert "Intended?" in item["text"]


def test_unused_params_key_is_tell_only_and_a_question():
    message = "'limitt': no phase lists this param, so it is ignored"
    item = recommend.classify("--params", "WARN", message)
    assert (item["kind"], item["action"]) == ("tell", "unused_param")
    assert item["text"].endswith("?")


def test_config_edits_are_offers():
    cases = {
        "missing `partitionable` (true or false)": "set_partitionable",
        "Duplicate phase name 'a:run': entries 1 and 3.": "rename_phase",
        "key 'by' is not used by strategy 'local'": "fix_execution",
        "missing `input:` block": "add_input",
        "cannot read 'x.parquet': nope": "new_sample",
        "cannot resolve 'a:b': No module named 'a'": "repick_path",
    }
    for message, action in cases.items():
        item = recommend.classify("P1", "FAIL", message)
        assert (item["kind"], item["action"]) == ("offer", action), message


def test_unknown_message_is_told_not_dropped():
    item = recommend.classify("P1", "FAIL", "something new")
    assert item["kind"] == "tell"
    assert "something new" in item["text"]


# ---- merge: unexpected + missing param is one rename ----


def test_unexpected_and_missing_param_merge_into_a_rename_offer():
    items = only([row("P1", "FAIL", "unexpected param 'limt' (signature: gdf, limit)",
                      "missing required param 'limit'")])
    assert len(items) == 1
    assert (items[0]["kind"], items[0]["action"]) == ("offer", "rename_param")
    assert (items[0]["old"], items[0]["new"]) == ("limt", "limit")
    assert items[0]["text"] == "Rename `limt` to `limit`?"


def test_rename_pairs_stay_inside_one_phase():
    items = only([row("P1", "FAIL", "unexpected param 'a' (signature: x)"),
                  row("P2", "FAIL", "missing required param 'b'")])
    assert [i["action"] for i in items] == ["remove_param", "add_param"]


def test_extra_unexpected_params_are_not_swallowed():
    items = only([row("P1", "FAIL", "unexpected param 'a' (signature: x, b)",
                      "unexpected param 'c' (signature: x, b)", "missing required param 'b'")])
    assert sorted(i["action"] for i in items) == ["remove_param", "rename_param"]


# ---- link: a crash after a dropped column points at the cause ----


def test_crash_names_the_earlier_dropped_column():
    items = only([row("P1", "WARN", "columns dropped: value"),
                  row("P2", "FAIL", "KeyError: 'value'")])
    crash = next(i for i in items if i["action"] == "crash")
    assert crash["cause"] == "P1"
    assert "`value` dropped in P1" in crash["text"]


def test_crash_is_not_linked_to_a_later_or_unrelated_drop():
    items = only([row("P1", "WARN", "columns dropped: zone"),
                  row("P2", "FAIL", "KeyError: 'value'"),
                  row("P3", "WARN", "columns dropped: value")])
    crash = next(i for i in items if i["action"] == "crash")
    assert "cause" not in crash


# ---- fold and order ----


def test_skips_fold_into_one_line_and_pass_is_one_last_line():
    items = only([row("P1", "PASS"), row("P2", "FAIL", "KeyError: 'x'"),
                  row("P3", "SKIP", "upstream phase failed"),
                  row("P4", "SKIP", "upstream phase failed"), row("input", "PASS")])
    assert [i["status"] for i in items] == ["FAIL", "SKIP", "PASS"]
    assert items[1]["text"] == "P3, P4 were not tested because an earlier phase failed."
    assert items[2]["text"] == "P1, input look fine."
    assert all(i["kind"] == "note" for i in items[1:])


def test_order_is_fail_then_warn_then_skip_then_pass_keeping_row_order():
    items = only([row("P1", "WARN", "CRS changed from a to b"),
                  row("P2", "FAIL", "KeyError: 'x'"), row("P3", "PASS"),
                  row("P4", "FAIL", "missing `partitionable` (true or false)"),
                  row("P5", "SKIP", "upstream phase failed")])
    assert [(i["label"], i["status"]) for i in items] == [
        ("P2", "FAIL"), ("P4", "FAIL"), ("P1", "WARN"), ("P5", "SKIP"), ("P3", "PASS")]


def test_no_pass_or_skip_lines_when_there_are_none():
    assert only([row("P1", "WARN", "CRS changed from a to b")])[0]["status"] == "WARN"
    assert len(only([row("P1", "WARN", "CRS changed from a to b")])) == 1


# ---- build-shim offer ----

CONFIG = """\
phases:
  - path: tidy_shim:run   # shim wraps phases.tidy:tidy
    partitionable: true
  - path: other:run
    partitionable: true
"""


def test_unresolved_path_with_shim_wraps_comment_offers_to_build_it():
    rows = [row("P1", "FAIL", "cannot resolve 'tidy_shim:run': No module named 'tidy_shim'"),
            row("P2", "FAIL", "cannot resolve 'other:run': No module named 'other'")]
    items = recommend.recommend({"rows": rows}, CONFIG)["items"]
    shim = next(i for i in items if i["label"] == "P1")
    assert (shim["kind"], shim["action"]) == ("offer", "build_shim")
    assert shim["wraps"] == "phases.tidy:tidy"
    assert shim["name"] == "tidy_shim"
    assert next(i for i in items if i["label"] == "P2")["action"] == "repick_path"


# ---- the deliberately broken fixture, end to end through real `check` ----


def actions(result):
    return {(i["label"], i["action"]) for i in result["items"]}


def test_broken_static_config_gets_the_expected_offers_and_notes(broken_repo):
    result = recommend.recommend_repo(broken_repo, "plumber.yaml", {"limitt": 5})
    assert actions(result) >= {
        ("P1", "rename_param"),
        ("P2", "build_shim"),
        ("P3", "set_partitionable"),
        ("--params", "unused_param"),
    }
    rename = next(i for i in result["items"] if i["action"] == "rename_param")
    assert (rename["old"], rename["new"]) == ("limt", "limit")
    shim = next(i for i in result["items"] if i["action"] == "build_shim")
    assert shim["wraps"] == "phases.tidy:tidy"
    statuses = [i["status"] for i in result["items"]]
    assert statuses == sorted(statuses, key=["FAIL", "WARN", "SKIP", "PASS"].index)
    assert result["items"][-1]["status"] == "PASS"  # input and output are fine


def test_broken_runtime_config_gets_offers_and_tell_only_notes(broken_repo):
    sample = load_helper("sample")
    gdf = sample.build_sample({"value": "int"}, rows=6)
    (broken_repo / ".plumber").mkdir()
    gdf.to_parquet(broken_repo / ".plumber" / "check_sample.parquet")

    result = recommend.recommend_repo(broken_repo, "plumber.runtime.yaml", {})

    by_action = {i["action"]: i for i in result["items"]}
    assert by_action["set_partitionable_false"]["kind"] == "offer"  # P1 is not chunk-safe
    assert by_action["set_partitionable_false"]["label"] == "P1"
    assert (by_action["crs_changed"]["kind"], by_action["crs_changed"]["label"]) == ("tell", "P2")
    assert by_action["dropped_columns"]["kind"] == "tell"
    assert by_action["dropped_columns"]["text"].endswith("Intended?")
    crash = by_action["crash"]
    assert (crash["kind"], crash["label"], crash["cause"]) == ("tell", "P4", "P3")
    assert by_action["skipped"]["text"].startswith("P5 were not tested")
    # every WARN on this (otherwise correct) pipeline is a question
    assert all(i["text"].endswith("?") for i in result["items"] if i["status"] == "WARN")
    assert [i["status"] for i in result["items"]][-1] == "PASS"


def test_config_that_does_not_load_is_one_offer(repo):
    (repo / "plumber.yaml").write_text("input: [not a mapping")
    items = recommend.recommend_repo(repo)["items"]
    assert [(i["status"], i["action"]) for i in items] == [("FAIL", "fix_config")]


def test_braces_in_a_check_message_do_not_break_classify():
    item = recommend.classify("P1", "FAIL", "KeyError: {'a': 1}")
    assert item["action"] == "crash"
    assert "{'a': 1}" in item["text"]


def test_shim_wraps_falls_back_to_the_shim_file(tmp_path):
    (tmp_path / ".plumber").mkdir()
    (tmp_path / ".plumber" / "tidy_shim.py").write_text(
        "# base: x\n# shim wraps phases.tidy:tidy\n"
    )
    rows = [row("P1", "FAIL", "cannot resolve 'tidy_shim:run': No module named 'tidy_shim'")]
    config = "phases:\n  - path: tidy_shim:run\n"
    items = recommend.recommend({"rows": rows}, config, tmp_path)["items"]
    assert items[0]["action"] == "build_shim"
    assert items[0]["wraps"] == "phases.tidy:tidy"


def test_malformed_config_that_loads_is_one_offer(repo):
    (repo / "plumber.yaml").write_text("input:\n  path: myio:load_fixture\nphases: nope\n")
    items = recommend.recommend_repo(repo)["items"]
    assert [(i["status"], i["action"]) for i in items] == [("FAIL", "fix_config")]
