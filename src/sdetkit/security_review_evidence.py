"""Collect GitHub security review evidence for PR quality narratives.

This module is advisory/read-only. It turns unresolved security review
threads into Sentinel-compatible findings so the Evidence Graph and PR Quality
narrative can treat security review as a first-class release-confidence signal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.security-review-evidence.v1"

SECURITY_AUTHOR_TOKENS = (
    "github-advanced-security",
    "sdetkit-security-gate",
)

SECURITY_BODY_TOKENS = (
    "github-advanced-security",
    "sdetkit-security-gate",
    "high entropy string",
    "secret",
    "secret-like",
    "vulnerability",
    "security gate",
    "fix or dismiss",
    "dismissing the alert",
)


JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _read_json(path: Path | None) -> JsonObject:
    if not path or not path.exists():
        return {}
    return _as_dict(json.loads(path.read_text(encoding="utf-8")))


def _write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _thread_nodes(payload: JsonObject) -> list[JsonObject]:
    pull_request = _as_dict(
        _as_dict(_as_dict(payload.get("data")).get("repository")).get("pullRequest")
    )
    threads = _as_dict(pull_request.get("reviewThreads"))
    return [_as_dict(item) for item in _as_list(threads.get("nodes")) if isinstance(item, dict)]


def _comment_nodes(thread: JsonObject) -> list[JsonObject]:
    comments = _as_dict(thread.get("comments"))
    return [_as_dict(item) for item in _as_list(comments.get("nodes")) if isinstance(item, dict)]


def _author_login(comment: JsonObject) -> str:
    return str(_as_dict(comment.get("author")).get("login", "")).lower()


def _is_security_comment(comment: JsonObject) -> bool:
    author = _author_login(comment)
    body = str(comment.get("body", "")).lower()
    return any(token in author for token in SECURITY_AUTHOR_TOKENS) or any(
        token in body for token in SECURITY_BODY_TOKENS
    )


def _summary(comment: JsonObject, path: str) -> str:
    body = " ".join(str(comment.get("body", "")).split())
    if len(body) > 180:
        body = body[:177].rstrip() + "..."
    if path:
        return f"Unresolved security review comment on {path}: {body}"
    return f"Unresolved security review comment: {body}"


def _finding_id(thread: JsonObject, comment: JsonObject) -> str:
    raw = "|".join(
        [
            str(thread.get("path", "")),
            str(thread.get("line", "")),
            str(comment.get("url", "")),
            str(comment.get("body", ""))[:120],
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"security-review-{digest}"


def findings_from_review_threads(payload: JsonObject) -> list[JsonObject]:
    findings: list[JsonObject] = []
    for thread in _thread_nodes(payload):
        if bool(thread.get("isResolved", False)) or bool(thread.get("isOutdated", False)):
            continue

        security_comments = [
            comment for comment in _comment_nodes(thread) if _is_security_comment(comment)
        ]
        if not security_comments:
            continue

        path = str(thread.get("path", "") or "")
        line = thread.get("line")
        comment = security_comments[-1]
        title = "Security review comment requires fix or dismissal"
        if path:
            title = f"Security review requires action in {path}"

        commands = [
            "Review unresolved GitHub Advanced Security comments on the PR.",
            "Fix the flagged surface or dismiss the false positive with a review reason.",
            "PYTHONPATH=src python -m pre_commit run -a",
        ]

        findings.append(
            {
                "finding_id": _finding_id(thread, comment),
                "title": title,
                "summary": _summary(comment, path),
                "risk_surface": "security",
                "severity": "warning",
                "review_first": True,
                "safe_to_auto_fix": False,
                "owner_files": [path] if path else [],
                "source_artifacts": ["build/pr-quality/security-review/review-threads.json"],
                "recommended_commands": commands,
                "proof_commands": commands[:2],
                "recurrence_state": "unknown",
                "operator_action": "review",
                "automation_allowed_now": False,
                "line": line,
                "comment_url": comment.get("url", ""),
                "author": _author_login(comment),
            }
        )

    return findings


def build_security_review_evidence(review_threads: Path | None) -> JsonObject:
    raw_payload = _read_json(review_threads)
    found = bool(raw_payload)
    findings = findings_from_review_threads(raw_payload)
    state = "warning" if findings else "healthy"
    collection_status = "collected" if found else "unavailable"
    return {
        "schema_version": SCHEMA_VERSION,
        "state": state,
        "collection_status": collection_status,
        "found": found,
        "automation_allowed_now": False,
        "automation_reason": "Security review evidence is advisory/read-only and requires human fix or dismissal.",
        "active_threat_count": len(findings),
        "active_threats": findings,
        "review_first_count": len(findings),
        "source_artifacts": {
            "review_threads": str(review_threads) if review_threads else "",
        },
    }


def merge_with_sentinel_control_room(
    sentinel_control_room: Path | None,
    security_evidence: JsonObject,
) -> JsonObject:
    base = dict(_read_json(sentinel_control_room))
    if not base:
        base = {
            "schema_version": "sdetkit.adaptive.sentinel.control_room.v1",
            "state": "healthy",
            "automation_allowed_now": False,
            "active_threats": [],
            "active_threat_count": 0,
            "review_first_count": 0,
            "source_artifacts": {},
        }

    existing = [_as_dict(item) for item in _as_list(base.get("active_threats"))]
    security_findings = [
        _as_dict(item) for item in _as_list(security_evidence.get("active_threats"))
    ]
    active = [*existing, *security_findings]

    base["active_threats"] = active
    base["active_threat_count"] = len(active)
    base["review_first_count"] = sum(1 for item in active if bool(item.get("review_first", False)))
    base["automation_allowed_now"] = False
    base["security_review_collection_status"] = security_evidence.get(
        "collection_status",
        "unknown",
    )
    base["security_review_finding_count"] = len(security_findings)

    if security_findings:
        base["state"] = (
            "warning" if str(base.get("state", "healthy")) == "healthy" else base.get("state")
        )
        base["security_review_state"] = "review_required"
    else:
        base.setdefault("security_review_state", "healthy")

    source_artifacts = _as_dict(base.get("source_artifacts"))
    source_artifacts["security_review_json"] = (
        "build/pr-quality/security-review/security-review.json"
    )
    source_artifacts["security_review_markdown"] = (
        "build/pr-quality/security-review/security-review.md"
    )
    base["source_artifacts"] = source_artifacts
    return base


def render_markdown(payload: JsonObject) -> str:
    findings = [_as_dict(item) for item in _as_list(payload.get("active_threats"))]
    lines = [
        "# Security Review Evidence",
        "",
        f"state: {payload.get('state', 'unknown')}",
        f"collection_status: {payload.get('collection_status', 'unknown')}",
        f"active_security_review_findings: {len(findings)}",
        "",
    ]
    if not findings:
        lines.append("No unresolved security review findings were collected.")
        return "\n".join(lines).rstrip() + "\n"

    for finding in findings:
        lines.extend(
            [
                f"## {finding.get('title', 'Security review finding')}",
                "",
                str(finding.get("summary", "")),
                "",
                f"- Risk surface: `{finding.get('risk_surface', 'security')}`",
                f"- Review first: `{str(finding.get('review_first', True)).lower()}`",
                f"- Automation allowed now: `{str(finding.get('automation_allowed_now', False)).lower()}`",
                "",
                "Recommended commands:",
            ]
        )
        for command in _as_list(finding.get("recommended_commands")):
            lines.append(f"- `{command}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.security_review_evidence")
    parser.add_argument("--review-threads-json", type=Path)
    parser.add_argument("--sentinel-control-room", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("build/pr-quality/security-review"))
    parser.add_argument("--merged-control-room", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    security = build_security_review_evidence(args.review_threads_json)
    _write_json(args.out_dir / "security-review.json", security)
    (args.out_dir / "security-review.md").write_text(render_markdown(security), encoding="utf-8")

    if args.merged_control_room:
        merged = merge_with_sentinel_control_room(args.sentinel_control_room, security)
        _write_json(args.merged_control_room, merged)

    print(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "state": security.get("state", "unknown"),
                "active_security_review_findings": security.get("active_threat_count", 0),
                "security_review_json": str(args.out_dir / "security-review.json"),
                "merged_control_room": str(args.merged_control_room or ""),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
