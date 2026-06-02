from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.security.inventory.v1"
DEFAULT_OUT = "build/sdetkit/security-findings-inventory.json"

AUTHORITY_BOUNDARY = {
    "automation_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}


def _load_dict(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _as_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = payload.get(key, [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _counts(payload: dict[str, Any]) -> dict[str, int]:
    raw = payload.get("counts", {})
    counts = raw if isinstance(raw, dict) else {}
    return {
        "error": _as_int(counts.get("error")),
        "warn": _as_int(counts.get("warn")),
        "info": _as_int(counts.get("info")),
    }


def _norm_text(value: object, default: str) -> str:
    text = str(value or "").strip()
    return text if text else default


def _finding_item(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": _norm_text(finding.get("path"), "unknown"),
        "rule": _norm_text(finding.get("rule_id", finding.get("rule")), "unknown"),
        "level": _norm_text(finding.get("severity", finding.get("level")), "unknown"),
        "line": _as_int(finding.get("line")),
        "column": _as_int(finding.get("column")),
        "message": _norm_text(finding.get("message"), ""),
        "needs_review": True,
        "dismiss_allowed": False,
        "fix_allowed": False,
        **AUTHORITY_BOUNDARY,
    }


def _top(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "count": count,
            "needs_review": True,
            **AUTHORITY_BOUNDARY,
        }
        for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def build_security_findings_inventory(security: dict[str, Any]) -> dict[str, Any]:
    findings = [_finding_item(item) for item in _as_list(security, "findings")]
    new_findings = [_finding_item(item) for item in _as_list(security, "new_findings")]
    counts = _counts(security)

    by_rule = Counter(str(item["rule"]) for item in findings)
    by_path = Counter(str(item["path"]) for item in findings)
    by_level = Counter(str(item["level"]) for item in findings)

    review_count = len(findings)
    if review_count == 0 and (counts["error"] or counts["warn"]):
        status = "counts need review"
    elif counts["error"]:
        status = "errors need review"
    elif findings or counts["warn"]:
        status = "warnings need review"
    else:
        status = "clean"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "source_count": counts,
        "actual_count": len(findings),
        "new_count": len(new_findings),
        "review_count": review_count,
        "by_rule": _top(by_rule),
        "by_path": _top(by_path),
        "by_level": _top(by_level),
        "items": findings,
        "new_items": new_findings,
        "recommended_action": "review grouped findings before any remediation or dismissal",
        "dismiss_allowed": False,
        "fix_allowed": False,
        **AUTHORITY_BOUNDARY,
    }


def write_security_findings_inventory_artifact(
    *,
    security_json: str | Path,
    out: str | Path = DEFAULT_OUT,
) -> dict[str, Any]:
    payload = build_security_findings_inventory(_load_dict(security_json))
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit security-findings-inventory",
        description="Build read-only grouped inventory from security check JSON.",
    )
    parser.add_argument("--security-json", required=True)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_security_findings_inventory_artifact(
        security_json=ns.security_json,
        out=ns.out,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"inventory_json={ns.out}\n")
        sys.stdout.write(f"status={payload['status']}\n")
        sys.stdout.write(f"actual_count={payload['actual_count']}\n")
        sys.stdout.write(f"review_count={payload['review_count']}\n")
        sys.stdout.write(f"dismiss_allowed={str(payload['dismiss_allowed']).lower()}\n")
        sys.stdout.write(f"fix_allowed={str(payload['fix_allowed']).lower()}\n")
        sys.stdout.write(f"automation_allowed={str(payload['automation_allowed']).lower()}\n")
        sys.stdout.write(f"merge_authorized={str(payload['merge_authorized']).lower()}\n")
        sys.stdout.write(
            f"semantic_equivalence_proven={str(payload['semantic_equivalence_proven']).lower()}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
