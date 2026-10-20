from pathlib import Path

import yaml

from conftest import SKILL_SCRIPTS
from plumber.check import check
from plumber.resolver import resolve

EXAMPLE = SKILL_SCRIPTS.parent / "templates" / "plumber.example.yaml"


def test_example_config_passes_check(repo):
    """The example runs against the fixture repo, so it cannot drift from plumber's schema."""
    config = yaml.safe_load(EXAMPLE.read_text())
    sample = Path(config["check"]["sample"])
    sample.parent.mkdir(exist_ok=True)
    resolve("myio:load_fixture")().to_parquet(sample)
    result = check(config)
    assert result["ok"] is True, [r for r in result["rows"] if r["status"] == "FAIL"]
    assert result["runtime_probe"].startswith("ran on")
