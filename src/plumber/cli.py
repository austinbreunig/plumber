"""The `plumber` command line."""

import argparse

from plumber.run import load_config, run


def main(argv=None):
    parser = argparse.ArgumentParser(prog="plumber")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run", help="run the pipeline in ./plumber.yaml")
    parser.parse_args(argv)

    run(load_config())
