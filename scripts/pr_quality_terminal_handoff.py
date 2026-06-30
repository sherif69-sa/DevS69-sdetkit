from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from pr_quality_terminal_core import number, text


def verify_handoff(
    path: Path,
    repository: str,
    pr_number: int,
    head_sha: str,
    run_id: int,
    run_attempt: int,
):
    root = path.parent
    expected_files = {
        "manifest.json",
        "payload/pr-comment-body.md",
        "payload/pr-comment-metadata.json",
        "payload/pr-review-summary.md",
        "payload/pr-review-model.json",
    }
    actual_files = set()
    for candidate in root.rglob("*"):
        if candidate.is_symlink():
            raise ValueError(f"publisher handoff contains a symlink: {candidate}")
        if candidate.is_file():
            relative = candidate.relative_to(root).as_posix()
            pure = PurePosixPath(relative)
            if pure.is_absolute() or ".." in pure.parts:
                raise ValueError(f"publisher handoff contains an unsafe path: {relative}")
            actual_files.add(relative)
    if actual_files != expected_files:
        raise ValueError("publisher handoff file allowlist mismatch")

    payload = json.loads(path.read_text())
    if payload.get("schema_version") != "sdetkit.pr_quality_publisher_handoff.v1":
        raise ValueError("publisher handoff schema mismatch")
    expected = {
        "repository": repository,
        "event_name": "pull_request",
        "pr_number": pr_number,
        "head_sha": head_sha,
        "source_workflow_name": "PR Quality Comment",
        "source_workflow_run_id": run_id,
        "source_workflow_run_attempt": run_attempt,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ValueError(f"publisher handoff mismatch: {key}")
    if payload.get("authority_boundary") != {
        "reporting_only": True,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }:
        raise ValueError("publisher handoff authority mismatch")

    allowed_payload = expected_files - {"manifest.json"}
    rows = payload.get("files")
    if not isinstance(rows, list) or len(rows) != len(allowed_payload):
        raise ValueError("publisher handoff manifest inventory mismatch")
    observed = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("publisher handoff file row must be an object")
        relative = text(row.get("path"))
        if relative not in allowed_payload:
            raise ValueError(f"publisher handoff path is not allowed: {relative}")
        observed.add(relative)
        data = (root / relative).read_bytes()
        if len(data) != number(row.get("size_bytes")):
            raise ValueError(f"publisher handoff size mismatch: {relative}")
        if hashlib.sha256(data).hexdigest() != text(row.get("sha256")):
            raise ValueError(f"publisher handoff digest mismatch: {relative}")
    if observed != allowed_payload:
        raise ValueError("publisher handoff manifest inventory is incomplete")

    summary = (root / "payload/pr-review-summary.md").read_text()
    if not summary.lstrip().startswith("# PR Quality Review Summary"):
        raise ValueError("publisher handoff summary contract mismatch")
    for relative in (
        "payload/pr-comment-metadata.json",
        "payload/pr-review-model.json",
    ):
        if not isinstance(json.loads((root / relative).read_text()), Mapping):
            raise ValueError(f"publisher handoff JSON object required: {relative}")
