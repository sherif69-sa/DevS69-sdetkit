from __future__ import annotations

import argparse


def build_review_forwarded_args(ns: argparse.Namespace) -> list[str]:
    forwarded = [ns.path]
    if ns.workspace_root:
        forwarded.extend(["--workspace-root", ns.workspace_root])
    if ns.out_dir:
        forwarded.extend(["--out-dir", ns.out_dir])
    if ns.profile:
        forwarded.extend(["--profile", ns.profile])
    if ns.format:
        forwarded.extend(["--format", ns.format])
    if ns.interactive:
        forwarded.append("--interactive")
    if ns.no_workspace:
        forwarded.append("--no-workspace")
    if ns.work_id:
        forwarded.extend(["--work-id", ns.work_id])
    for entry in ns.work_context or []:
        forwarded.extend(["--work-context", entry])
    if ns.code_scan_json:
        forwarded.extend(["--code-scan-json", ns.code_scan_json])
    return forwarded
