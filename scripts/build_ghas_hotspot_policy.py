#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "sdetkit.ghas.hotspot_policy.v1"
FIXTURE_PREFIXES = ("tests/fixtures/", "examples/fixtures/", "docs/fixtures/")


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def alert_path(alert: dict[str, Any]) -> str:
    instance = _dict(alert.get("most_recent_instance"))
    location = _dict(instance.get("location"))
    value = str(location.get("path") or alert.get("path") or "unknown")
    return value.replace("\\", "/").removeprefix("./") or "unknown"


def is_fixture_path(path: str) -> bool:
    return path.lower().startswith(FIXTURE_PREFIXES)


def _age(alert: dict[str, Any], now: datetime) -> int:
    raw = alert.get("created_at") or alert.get("updated_at") or alert.get("fixed_at")
    if not raw:
        return 0
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return 0
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return max(0, int((now - value.astimezone(UTC)).total_seconds() // 86400))


def summarize(alerts: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    rules: dict[str, dict[str, Any]] = {}
    files: Counter[str] = Counter()
    severity: Counter[str] = Counter()
    aged14 = 0
    aged30 = 0
    for alert in alerts:
        rule = _dict(alert.get("rule"))
        tool = _dict(alert.get("tool"))
        rule_id = str(rule.get("id") or rule.get("name") or "unknown-rule")
        level = str(
            rule.get("security_severity_level") or rule.get("severity") or "unknown"
        ).lower()
        age = _age(alert, now)
        bucket = rules.setdefault(
            rule_id,
            {
                "key": rule_id,
                "rule_name": str(rule.get("name") or rule_id),
                "tool": str(tool.get("name") or "unknown-tool"),
                "severity": level,
                "count": 0,
                "oldest_age_days": 0,
            },
        )
        bucket["count"] += 1
        bucket["oldest_age_days"] = max(bucket["oldest_age_days"], age)
        files[alert_path(alert)] += 1
        severity[level] += 1
        aged14 += int(age >= 14)
        aged30 += int(age >= 30)
    top_rules = sorted(
        rules.values(),
        key=lambda row: (-row["count"], -row["oldest_age_days"], row["key"]),
    )[:10]
    top_files = [
        {"file": path, "count": count}
        for path, count in sorted(files.items(), key=lambda row: (-row[1], row[0]))[:10]
    ]
    return {
        "alert_count": len(alerts),
        "alerts_aged_14_days_or_more": aged14,
        "alerts_aged_30_days_or_more": aged30,
        "top_rules": top_rules,
        "top_files": top_files,
        "severity": dict(sorted(severity.items())),
    }


def build_policy(payload: Any, now: datetime | None = None) -> tuple[dict[str, Any], str]:
    data = _dict(payload)
    status = str(data.get("collection_status") or "unavailable")
    alerts = [_dict(item) for item in _list(data.get("alerts")) if _dict(item)]
    current = now or datetime.now(UTC)
    fixture_alerts = [item for item in alerts if is_fixture_path(alert_path(item))]
    production_alerts = [item for item in alerts if not is_fixture_path(alert_path(item))]
    reasons: list[str] = []
    if status != "collected":
        reasons.append("code-scanning alert collection is unavailable")
    if production_alerts:
        reasons.append(f"production-path code-scanning alerts: {len(production_alerts)}")
    snapshot = {
        "schema_version": SCHEMA,
        "generated_at": current.isoformat(),
        "repository": str(data.get("repository") or "unknown"),
        "collection_status": status,
        "actionable": bool(reasons),
        "actionable_reasons": reasons,
        "issue_policy": "rolling_tracker_when_production_or_collection_failure",
        "fixture_only_issue_creation": False,
        "totals": {
            "open_alerts": len(alerts),
            "production_alerts": len(production_alerts),
            "fixture_alerts": len(fixture_alerts),
        },
        "production": summarize(production_alerts, current),
        "fixture_evidence": summarize(fixture_alerts, current),
        "fixture_prefixes": list(FIXTURE_PREFIXES),
        "notes": [str(item) for item in _list(data.get("notes")) if str(item).strip()],
    }
    return snapshot, render_markdown(snapshot)


def _file_lines(rows: list[dict[str, Any]], empty: str) -> list[str]:
    return (
        [f"- **{row['file']}** — {row['count']} alert(s)" for row in rows]
        if rows
        else [f"- {empty}"]
    )


def render_markdown(snapshot: dict[str, Any]) -> str:
    totals = snapshot["totals"]
    production = snapshot["production"]
    fixture = snapshot["fixture_evidence"]
    lines = [
        "# GHAS production hotspot review",
        "",
        "This report separates production-path alerts from intentional fixture evidence.",
        "",
        "## Classification snapshot",
        f"- Collection status: **{snapshot['collection_status']}**",
        f"- Open alerts: **{totals['open_alerts']}**",
        f"- Production-path alerts: **{totals['production_alerts']}**",
        f"- Fixture-only alerts: **{totals['fixture_alerts']}**",
        f"- Actionable: **{snapshot['actionable']}**",
        "",
        "## Production files",
        *_file_lines(production["top_files"], "No production-path hotspots were returned."),
        "",
        "## Fixture evidence (non-production)",
        f"- Retained alerts: **{fixture['alert_count']}**",
        *_file_lines(fixture["top_files"], "No fixture-only alerts were returned."),
        "",
    ]
    if snapshot["actionable"]:
        lines.extend(
            [
                "## Required follow-up",
                *[f"- {reason}" for reason in snapshot["actionable_reasons"]],
                "- Review production paths first; do not modify intentional fixtures merely to clear GHAS counts.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Result",
                "- No production-path remediation issue is required.",
                "- Fixture findings remain available in the uploaded artifact for scanner-regression proof.",
                "",
            ]
        )
    lines.extend(
        [
            "## Artifact",
            "- `build/ghas-codeql-hotspots.json`",
            "- `build/ghas-codeql-hotspots.md`",
            "",
            "## Notes",
            *(
                [f"- {note}" for note in snapshot["notes"]]
                if snapshot["notes"]
                else ["- Code-scanning APIs responded without fallback warnings."]
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alerts-json", type=Path, required=True)
    parser.add_argument("--snapshot-json", type=Path, required=True)
    parser.add_argument("--report-markdown", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    snapshot, markdown = build_policy(json.loads(args.alerts_json.read_text(encoding="utf-8")))
    args.snapshot_json.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.report_markdown.write_text(markdown, encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"actionable={'true' if snapshot['actionable'] else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
