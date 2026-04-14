from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_inspect_compare_forwarded_args(
    ns: argparse.Namespace, args: Sequence[str] | None = None
) -> list[str]:
    forwarded = list(args or [])
    if ns.left:
        forwarded = ["--left", ns.left, *forwarded]
    if ns.right:
        forwarded = ["--right", ns.right, *forwarded]
    if ns.left_run:
        forwarded = ["--left-run", ns.left_run, *forwarded]
    if ns.right_run:
        forwarded = ["--right-run", ns.right_run, *forwarded]
    if ns.scope:
        forwarded = ["--scope", ns.scope, *forwarded]
    if ns.latest_vs_previous:
        forwarded = ["--latest-vs-previous", *forwarded]
    if ns.workspace_root:
        forwarded = ["--workspace-root", ns.workspace_root, *forwarded]
    if ns.workflow:
        forwarded = ["--workflow", ns.workflow, *forwarded]
    if ns.format:
        forwarded = ["--format", ns.format, *forwarded]
    if ns.out_dir:
        forwarded = ["--out-dir", ns.out_dir, *forwarded]
    if ns.no_workspace:
        forwarded = ["--no-workspace", *forwarded]
    return forwarded
