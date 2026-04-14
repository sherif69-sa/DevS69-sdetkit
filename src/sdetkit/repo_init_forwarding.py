from __future__ import annotations

import argparse


def build_repo_init_forwarded_args(ns: argparse.Namespace) -> list[str]:
    forwarded = [
        "init",
        "--preset",
        ns.preset,
        "--root",
        ns.root,
        "--format",
        ns.format,
    ]
    if ns.dry_run:
        forwarded.append("--dry-run")
    if ns.force:
        forwarded.append("--force")
    if ns.diff:
        forwarded.append("--diff")
    if ns.write_config:
        forwarded.append("--write-config")
    return forwarded
