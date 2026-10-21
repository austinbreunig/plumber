def test_skill_api_importable_from_top_level():
    from plumber import check, format_report, load_config  # noqa: F401
