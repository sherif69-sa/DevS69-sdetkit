from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_inspect_forwarded_args(ns: argparse.Namespace, args: Sequence[str] | None = None) -> list[str]:
    inspect_args = list(args or [])
    if ns.rules_template:
        inspect_args = ["--rules-template", *inspect_args]
    if ns.rules_lint:
        inspect_args = ["--rules-lint", ns.rules_lint, *inspect_args]
    return inspect_args
