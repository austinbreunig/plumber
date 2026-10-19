from conftest import load_helper

detect_case = load_helper("detect_case")


def test_draft_wins_over_everything(repo):
    (repo / "plumber.draft.yaml").write_text("# base: none\n" + (repo / "plumber.yaml").read_text())
    (repo / "plumber.yaml").write_text("input: [not a mapping")  # broken, still resume
    assert detect_case.detect_case(repo)["case"] == "resume"


def test_broken_draft_is_resume_with_the_error(repo):
    (repo / "plumber.draft.yaml").write_text("input: [not a mapping")
    result = detect_case.detect_case(repo)
    assert result["case"] == "resume"
    assert result["draft_error"]


def test_good_draft_has_no_error(repo):
    (repo / "plumber.draft.yaml").write_text((repo / "plumber.yaml").read_text())
    assert detect_case.detect_case(repo)["draft_error"] is None


def test_no_config_is_case_a_not_an_error(repo):
    (repo / "plumber.yaml").unlink()
    result = detect_case.detect_case(repo)
    assert result["case"] == "A"


def test_clean_config_is_case_b(repo):
    result = detect_case.detect_case(repo)
    assert result["case"] == "B"
    assert result["findings"] == []


def test_unloadable_config_is_case_c(repo):
    (repo / "plumber.yaml").write_text("input: [not a mapping")
    result = detect_case.detect_case(repo)
    assert result["case"] == "C"
    assert "does not load" in result["findings"][0]


def test_check_fail_is_case_c(repo):
    text = (repo / "plumber.yaml").read_text().replace("phases.scale_value", "phases.nope")
    (repo / "plumber.yaml").write_text(text)
    result = detect_case.detect_case(repo)
    assert result["case"] == "C"
    assert any("FAIL" in line for line in result["findings"])


def test_check_warn_is_case_c(repo):
    import geopandas as gpd
    from shapely.geometry import Point

    gpd.GeoDataFrame(
        {"value": [1, 2], "geometry": [Point(0, 0), Point(1, 1)]}, crs="EPSG:4326"
    ).to_parquet(repo / "sample.parquet")
    text = (repo / "plumber.yaml").read_text()
    text = text.replace("phases.scale_value:run", "phases.drop_value:run")
    text = text.replace("params: {factor: 2}", "params: {}")
    (repo / "plumber.yaml").write_text(text + "\ncheck:\n  sample: sample.parquet\n")
    result = detect_case.detect_case(repo)
    assert result["case"] == "C"
    assert any("WARN" in line for line in result["findings"])
