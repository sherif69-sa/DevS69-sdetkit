from __future__ import annotations

import argparse

from sdetkit.inspect_forwarding import build_inspect_forwarded_args


def test_build_inspect_forwarded_args_with_rules_flags() -> None:
    ns = argparse.Namespace(rules_template=True, rules_lint="lint.json")
    assert build_inspect_forwarded_args(ns, ["input.csv"]) == [
        "--rules-lint",
        "lint.json",
        "--rules-template",
        "input.csv",
    ]


def test_build_inspect_forwarded_args_without_rules_flags() -> None:
    ns = argparse.Namespace(rules_template=False, rules_lint="")
    assert build_inspect_forwarded_args(ns, ["input.csv"]) == ["input.csv"]
