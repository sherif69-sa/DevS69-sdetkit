from __future__ import annotations

import argparse

from sdetkit.review_forwarding import build_review_forwarded_args


def test_build_review_forwarded_args_includes_optional_values() -> None:
    ns = argparse.Namespace(
        path=".",
        workspace_root="/tmp/ws",
        out_dir="build",
        profile="strict",
        format="json",
        interactive=True,
        no_workspace=True,
        work_id="abc",
        work_context=["ticket=123"],
        code_scan_json="scan.json",
    )
    forwarded = build_review_forwarded_args(ns)
    assert forwarded == [
        ".",
        "--workspace-root",
        "/tmp/ws",
        "--out-dir",
        "build",
        "--profile",
        "strict",
        "--format",
        "json",
        "--interactive",
        "--no-workspace",
        "--work-id",
        "abc",
        "--work-context",
        "ticket=123",
        "--code-scan-json",
        "scan.json",
    ]


def test_build_review_forwarded_args_minimal() -> None:
    ns = argparse.Namespace(
        path="repo",
        workspace_root="",
        out_dir="",
        profile="",
        format="",
        interactive=False,
        no_workspace=False,
        work_id="",
        work_context=[],
        code_scan_json="",
    )
    assert build_review_forwarded_args(ns) == ["repo"]
