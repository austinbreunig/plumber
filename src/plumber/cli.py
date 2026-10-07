"""The `plumber` command line."""

import argparse

import yaml

from plumber.check import check, format_report, write_report
from plumber.run import load_config, run


def parse_params(pairs):
    """Turn ["a=1", "b=x"] into {"a": 1, "b": "x"}. Values are read as YAML (1 is an int)."""
    params = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not (key and sep):
            raise SystemExit(f"Bad --params {pair!r}: expected key=value")
        params[key] = yaml.safe_load(value)
    return params


def main(argv=None):
    parser = argparse.ArgumentParser(prog="plumber")
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="run the pipeline in a config file")
    check_parser = commands.add_parser("check", help="check the config without running phases")
    for sub in (run_parser, check_parser):
        sub.add_argument("--config", default="plumber.yaml", help="default: ./plumber.yaml")
        sub.add_argument(
            "--params",
            nargs="+",
            default=[],
            metavar="key=value",
            help="override phase params (applies to every phase that has that param)",
        )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    overrides = parse_params(args.params)
    if args.command == "check":
        report = check(config, overrides)
        print(format_report(report))
        write_report(report)
        if not report["ok"]:
            raise SystemExit(1)
    else:
        run(config, overrides)
