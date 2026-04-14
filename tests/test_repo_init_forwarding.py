from __future__ import annotations

import argparse

from sdetkit.repo_init_forwarding import build_repo_init_forwarded_args


def test_build_repo_init_forwarded_args_includes_optional_flags() -> None:
    ns = argparse.Namespace(
        preset="minimal",
        root=".",
        format="text",
        dry_run=True,
        force=True,
        diff=True,
        write_config=True,
    )
    forwarded = build_repo_init_forwarded_args(ns)
    assert forwarded == [
        "init",
        "--preset",
        "minimal",
        "--root",
        ".",
        "--format",
        "text",
        "--dry-run",
        "--force",
        "--diff",
        "--write-config",
    ]


def test_build_repo_init_forwarded_args_omits_optional_flags_when_false() -> None:
    ns = argparse.Namespace(
        preset="strict",
        root="repo",
        format="json",
        dry_run=False,
        force=False,
        diff=False,
        write_config=False,
    )
    forwarded = build_repo_init_forwarded_args(ns)
    assert forwarded == [
        "init",
        "--preset",
        "strict",
        "--root",
        "repo",
        "--format",
        "json",
    ]
