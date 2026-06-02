from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.security.followup.disposition.v1"
DEFAULT_OUT = "build/sdetkit/security-followup-disposition.json"

AUTHORITY_BOUNDARY = {
    "automation_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}


def _load_json(path: str | Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_issues(path: str | Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if isinstance(payload, list):
        raw_issues = payload
    elif isinstance(payload, dict) and isinstance(payload.get("issues"), list):
        raw_issues = payload["issues"]
    else:
        raise ValueError("issues JSON must be a list or an object with an issues list")
    return [item for item in raw_issues if isinstance(item, dict)]


def _load_security(path: str | Path) -> dict[str, Any]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("security JSON must be an object")
    return payload


def _labels(issue: dict[str, Any]) -> list[str]:
    raw = issue.get("labels", [])
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for item in raw:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(str(item["name"]))
    return sorted({name.strip().lower() for name in names if name.strip()})


def _issue_number(issue: dict[str, Any]) -> int:
    value = issue.get("issue_number", issue.get("number", 0))
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _issue_text(issue: dict[str, Any], labels: list[str]) -> str:
    return "\n".join(
        [
            str(issue.get("title", "")),
            str(issue.get("body", "")),
            " ".join(labels),
        ]
    ).lower()


def _is_security_followup(issue: dict[str, Any]) -> bool:
    labels = _labels(issue)
    text = _issue_text(issue, labels)
    return (
        "security" in labels
        or "ghas" in labels
        or "security" in text
        or "actionable findings" in text
        or "autopilot" in text
    )


def _claimed_actionable_count(issue: dict[str, Any]) -> int:
    text = _issue_text(issue, _labels(issue))
    match = re.search(r"actionable findings:\s*(\d+)", text)
    if match is None:
        return 0
    try:
        return int(match.group(1))
    except ValueError:
        return 0


def _security_counts(security: dict[str, Any]) -> dict[str, int]:
    raw_counts = security.get("counts", {})
    counts = raw_counts if isinstance(raw_counts, dict) else {}

    def as_int(name: str) -> int:
        try:
            return int(counts.get(name, 0))
        except (TypeError, ValueError):
            return 0

    return {
        "error": as_int("error"),
        "warn": as_int("warn"),
        "info": as_int("info"),
    }


def _finding_count(security: dict[str, Any], field: str) -> int:
    raw = security.get(field, [])
    return len(raw) if isinstance(raw, list) else 0


def _findings_by_severity(security: dict[str, Any]) -> dict[str, int]:
    raw = security.get("findings", [])
    findings = raw if isinstance(raw, list) else []
    counts = {"error": 0, "warn": 0, "info": 0}
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        severity = str(finding.get("severity", "")).lower()
        if severity in counts:
            counts[severity] += 1
    return counts


def _disposition_for(
    *,
    claimed_actionable: int,
    counts: dict[str, int],
    current_finding_count: int,
    new_finding_count: int,
) -> tuple[str, bool, bool, str]:
    if counts["error"] > 0:
        return (
            "active blocker",
            True,
            False,
            "fix current security errors before closing the follow up",
        )
    if current_finding_count > 0 or new_finding_count > 0 or counts["warn"] > 0:
        return (
            "needs review",
            True,
            False,
            "review current security warnings and record a human disposition",
        )
    if claimed_actionable > 0:
        return (
            "ready with proof",
            False,
            True,
            "attach clean security proof before closing the follow up",
        )
    return (
        "no action needed",
        False,
        True,
        "retain as evidence only",
    )


def build_security_followup_disposition(
    issues: list[dict[str, Any]],
    security: dict[str, Any],
) -> dict[str, Any]:
    counts = _security_counts(security)
    severity_counts = _findings_by_severity(security)
    current_finding_count = _finding_count(security, "findings")
    new_finding_count = _finding_count(security, "new_findings")

    dispositions: list[dict[str, Any]] = []
    for issue in issues:
        if not _is_security_followup(issue):
            continue
        claimed_actionable = _claimed_actionable_count(issue)
        disposition, review_required, close_candidate, action = _disposition_for(
            claimed_actionable=claimed_actionable,
            counts=counts,
            current_finding_count=current_finding_count,
            new_finding_count=new_finding_count,
        )
        dispositions.append(
            {
                "issue_number": _issue_number(issue),
                "title": str(issue.get("title", "")),
                "claimed_actionable_findings": claimed_actionable,
                "security_error_count": counts["error"],
                "security_warn_count": counts["warn"],
                "security_info_count": counts["info"],
                "current_finding_count": current_finding_count,
                "new_finding_count": new_finding_count,
                "disposition": disposition,
                "review_required": review_required,
                "close_candidate": close_candidate,
                "recommended_action": action,
                **AUTHORITY_BOUNDARY,
            }
        )

    dispositions.sort(
        key=lambda item: (
            not bool(item["review_required"]),
            -int(item["claimed_actionable_findings"]),
            int(item["issue_number"]),
        )
    )
    primary = dispositions[0] if dispositions else None

    if any(bool(item["review_required"]) for item in dispositions):
        status = "review required"
    elif dispositions:
        status = "ready with proof"
    else:
        status = "no security followups"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "source_issue_count": len(issues),
        "security_followup_count": len(dispositions),
        "security_counts": counts,
        "finding_severity_counts": severity_counts,
        "current_finding_count": current_finding_count,
        "new_finding_count": new_finding_count,
        "dispositions": dispositions,
        "primary_issue": primary["issue_number"] if primary else None,
        "recommended_next_action": primary["recommended_action"] if primary else None,
        **AUTHORITY_BOUNDARY,
    }


def write_security_followup_disposition_artifact(
    *,
    issues_json: str | Path,
    security_json: str | Path,
    out: str | Path = DEFAULT_OUT,
) -> dict[str, Any]:
    payload = build_security_followup_disposition(
        _load_issues(issues_json),
        _load_security(security_json),
    )
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit security-followup-disposition",
        description="Build read-only disposition evidence for security follow-up issues.",
    )
    parser.add_argument("--issues-json", required=True)
    parser.add_argument("--security-json", required=True)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_security_followup_disposition_artifact(
        issues_json=ns.issues_json,
        security_json=ns.security_json,
        out=ns.out,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"security_followup_disposition_json={ns.out}\n")
        sys.stdout.write(f"status={payload['status']}\n")
        sys.stdout.write(f"security_followups={payload['security_followup_count']}\n")
        sys.stdout.write(f"primary_issue={payload['primary_issue']}\n")
        sys.stdout.write(f"automation_allowed={str(payload['automation_allowed']).lower()}\n")
        sys.stdout.write(f"merge_authorized={str(payload['merge_authorized']).lower()}\n")
        sys.stdout.write(
            f"semantic_equivalence_proven={str(payload['semantic_equivalence_proven']).lower()}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
