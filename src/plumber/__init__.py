"""plumber: geospatial pipelines with swappable execution strategies."""

from plumber.check import check, format_report
from plumber.run import load_config

__version__ = "0.1.2"

__all__ = ["__version__", "check", "format_report", "load_config"]
