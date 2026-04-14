from __future__ import annotations

import argparse


def build_inspect_project_forwarded_args(ns: argparse.Namespace) -> list[str]:
    forwarded = [ns.project_dir]
    if ns.policy:
        forwarded.extend(["--policy", ns.policy])
    if ns.workspace_root:
        forwarded.extend(["--workspace-root", ns.workspace_root])
    if ns.out_dir:
        forwarded.extend(["--out-dir", ns.out_dir])
    if ns.format:
        forwarded.extend(["--format", ns.format])
    if ns.no_workspace:
        forwarded.append("--no-workspace")
    return forwarded
