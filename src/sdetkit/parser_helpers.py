from __future__ import annotations

import argparse


def add_passthrough_subcommand(
    sub,
    name: str,
    *,
    help_text: str | None = None,
    aliases: list[str] | None = None,
    default_cmd: str | None = None,
):
    kwargs: dict[str, object] = {}
    if help_text is not None:
        kwargs["help"] = help_text
    if aliases:
        kwargs["aliases"] = aliases
    parser = sub.add_parser(name, **kwargs)
    if default_cmd is not None:
        parser.set_defaults(cmd=default_cmd)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    return parser
