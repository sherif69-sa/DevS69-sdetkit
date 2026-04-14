from __future__ import annotations

import argparse

from sdetkit.parser_helpers import add_passthrough_subcommand


def test_add_passthrough_subcommand_sets_default_cmd_and_args() -> None:
    parser = argparse.ArgumentParser(prog="x")
    sub = parser.add_subparsers(dest="command")
    add_passthrough_subcommand(sub, "demo", default_cmd="demo-cmd")

    ns = parser.parse_args(["demo", "a", "b"])
    assert ns.command == "demo"
    assert ns.cmd == "demo-cmd"
    assert ns.args == ["a", "b"]
