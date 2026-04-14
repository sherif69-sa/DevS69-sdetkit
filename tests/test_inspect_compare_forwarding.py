from __future__ import annotations

import argparse

from sdetkit.inspect_compare_forwarding import build_inspect_compare_forwarded_args


def test_build_inspect_compare_forwarded_args_full() -> None:
    ns = argparse.Namespace(
        left="left.json",
        right="right.json",
        left_run="a1",
        right_run="b2",
        scope="critical",
        latest_vs_previous=True,
        workspace_root="/tmp/ws",
        workflow="nightly",
        format="json",
        out_dir="build",
        no_workspace=True,
    )
    forwarded = build_inspect_compare_forwarded_args(ns, ["--strict"])
    assert forwarded == [
        "--no-workspace",
        "--out-dir",
        "build",
        "--format",
        "json",
        "--workflow",
        "nightly",
        "--workspace-root",
        "/tmp/ws",
        "--latest-vs-previous",
        "--scope",
        "critical",
        "--right-run",
        "b2",
        "--left-run",
        "a1",
        "--right",
        "right.json",
        "--left",
        "left.json",
        "--strict",
    ]


def test_build_inspect_compare_forwarded_args_minimal() -> None:
    ns = argparse.Namespace(
        left="",
        right="",
        left_run="",
        right_run="",
        scope="",
        latest_vs_previous=False,
        workspace_root="",
        workflow="",
        format="",
        out_dir="",
        no_workspace=False,
    )
    assert build_inspect_compare_forwarded_args(ns, ["a"]) == ["a"]
