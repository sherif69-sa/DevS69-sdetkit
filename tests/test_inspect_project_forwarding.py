from __future__ import annotations

import argparse

from sdetkit.inspect_project_forwarding import build_inspect_project_forwarded_args


def test_build_inspect_project_forwarded_args_full() -> None:
    ns = argparse.Namespace(
        project_dir="repo",
        policy="strict",
        workspace_root="/tmp/ws",
        out_dir="build",
        format="json",
        no_workspace=True,
    )
    assert build_inspect_project_forwarded_args(ns) == [
        "repo",
        "--policy",
        "strict",
        "--workspace-root",
        "/tmp/ws",
        "--out-dir",
        "build",
        "--format",
        "json",
        "--no-workspace",
    ]


def test_build_inspect_project_forwarded_args_minimal() -> None:
    ns = argparse.Namespace(
        project_dir="repo",
        policy="",
        workspace_root="",
        out_dir="",
        format="",
        no_workspace=False,
    )
    assert build_inspect_project_forwarded_args(ns) == ["repo"]
