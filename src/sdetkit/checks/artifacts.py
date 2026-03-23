from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .base import CheckProfileName
from .results import CheckRecord, FinalVerdict, build_final_verdict
from .runner import CheckRunReport

VERDICT_SCHEMA_VERSION = "sdetkit.artifacts.verdict.v1"
FIX_PLAN_SCHEMA_VERSION = "sdetkit.artifacts.fix-plan.v1"
RISK_SUMMARY_SCHEMA_VERSION = "sdetkit.artifacts.risk-summary.v1"
EVIDENCE_SCHEMA_VERSION = "sdetkit.artifacts.evidence.v1"

_SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}
_OWNER_HINTS = {
    "format": "developer-experience",
    "lint": "developer-experience",
    "typing": "python-platform",
    "tests": "quality-engineering",
    "security": "security",
    "doctor": "platform-ops",
    "repo": "repository-maintainers",
    "artifacts": "release-engineering",
}
_ACTION_HINTS = {
    "format_check": "Run `python -m ruff format .` and re-run validation.",
    "lint": "Run `python -m ruff check . --fix` where safe, then re-run validation.",
    "typing": "Repair mypy-reported typing issues and re-run the typing lane.",
    "tests_smoke": "Fix the smoke gate failure and then re-run the quick lane.",
    "tests_full": "Fix the failing test cases and re-run the full pytest truth path.",
    "doctor_core": "Review the doctor report and address the highest-severity checks first.",
    "security_source_scan": "Triage security findings and remediate high-risk items before merge.",
}


@dataclass(frozen=True)
class ArtifactPaths:
    verdict_json: Path
    summary_md: Path
    fix_plan_json: Path
    risk_summary_json: Path
    evidence_zip: Path
    run_report_json: Path


def artifact_paths_for(out_dir: Path) -> ArtifactPaths:
    return ArtifactPaths(
        verdict_json=out_dir / "verdict.json",
        summary_md=out_dir / "summary.md",
        fix_plan_json=out_dir / "fix-plan.json",
        risk_summary_json=out_dir / "risk-summary.json",
        evidence_zip=out_dir / "evidence.zip",
        run_report_json=out_dir / "run-report.json",
    )


def render_report_artifacts(
    report: CheckRunReport,
    *,
    repo_root: Path,
    out_dir: Path,
    paths: ArtifactPaths | None = None,
) -> dict[str, Any]:
    return _render_artifacts(
        records=report.records,
        verdict=report.verdict,
        report_payload=report.as_dict(),
        repo_root=repo_root,
        out_dir=out_dir,
        paths=paths or artifact_paths_for(out_dir),
    )


def render_record_artifacts(
    *,
    repo_root: Path,
    out_dir: Path,
    profile: str,
    records: tuple[CheckRecord, ...] | list[CheckRecord],
    requested_profile: str | None = None,
    profile_notes: str = "",
    metadata: dict[str, Any] | None = None,
    paths: ArtifactPaths | None = None,
) -> dict[str, Any]:
    merged_metadata = dict(metadata or {})
    if requested_profile is not None:
        merged_metadata.setdefault("requested_profile", requested_profile)
    verdict = build_final_verdict(
        profile=cast(CheckProfileName, profile),
        checks=list(records),
        profile_notes=profile_notes,
        metadata=merged_metadata,
    )
    report_payload = {
        **verdict.as_dict(),
        "plan": {
            "profile": verdict.profile,
            "requested_profile": requested_profile or verdict.profile,
            "selected_checks": [],
            "skipped_checks": [],
            "notes": [profile_notes] if profile_notes else [],
            "planner_selected": bool(requested_profile and requested_profile != verdict.profile),
            "changed_files": list(merged_metadata.get("changed_files", [])),
            "changed_areas": list(merged_metadata.get("changed_areas", [])),
            "adaptive_reason": str(merged_metadata.get("adaptive_reason", "")),
        },
    }
    return _render_artifacts(
        records=tuple(records),
        verdict=verdict,
        report_payload=report_payload,
        repo_root=repo_root,
        out_dir=out_dir,
        paths=paths or artifact_paths_for(out_dir),
    )


def _render_artifacts(
    *,
    records: tuple[CheckRecord, ...] | list[CheckRecord],
    verdict: FinalVerdict,
    report_payload: dict[str, Any],
    repo_root: Path,
    out_dir: Path,
    paths: ArtifactPaths,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ordered_records = tuple(records)
    artifact_map = {
        "verdict_json": str(paths.verdict_json),
        "summary_md": str(paths.summary_md),
        "fix_plan_json": str(paths.fix_plan_json),
        "risk_summary_json": str(paths.risk_summary_json),
        "evidence_zip": str(paths.evidence_zip),
        "run_report_json": str(paths.run_report_json),
    }
    verdict_payload = build_verdict_payload(
        verdict=verdict,
        records=ordered_records,
        artifact_paths=artifact_map,
    )
    fix_plan = build_fix_plan_payload(verdict_payload)
    risk_summary = build_risk_summary_payload(verdict_payload, fix_plan)
    summary_md = build_summary_markdown(verdict_payload, fix_plan)
    run_report_payload = {
        **report_payload,
        "artifact_paths": artifact_map,
    }

    paths.verdict_json.write_text(_stable_json(verdict_payload), encoding="utf-8")
    paths.summary_md.write_text(summary_md, encoding="utf-8")
    paths.fix_plan_json.write_text(_stable_json(fix_plan), encoding="utf-8")
    paths.risk_summary_json.write_text(_stable_json(risk_summary), encoding="utf-8")
    paths.run_report_json.write_text(_stable_json(run_report_payload), encoding="utf-8")
    write_evidence_zip(
        repo_root=repo_root,
        out_dir=out_dir,
        paths=paths,
        verdict_payload=verdict_payload,
        fix_plan=fix_plan,
        risk_summary=risk_summary,
        summary_md=summary_md,
        run_report_payload=run_report_payload,
        records=ordered_records,
    )
    return {
        "verdict": verdict_payload,
        "fix_plan": fix_plan,
        "risk_summary": risk_summary,
        "summary_markdown": summary_md,
        "artifact_paths": artifact_map,
    }


def build_verdict_payload(
    *,
    verdict: FinalVerdict,
    records: tuple[CheckRecord, ...] | list[CheckRecord],
    artifact_paths: dict[str, str],
) -> dict[str, Any]:
    record_items = [serialize_record(record) for record in records]
    check_summary = _check_results_summary(record_items)
    blockers = [
        {
            "check_id": item["id"],
            "title": item["title"],
            "category": item["category"],
            "severity": _severity_for_record(item),
            "reason": item["reason"] or "blocking failure",
            "target_mode": item["target_mode"],
            "related_files": item["related_files"],
            "log_path": item["log_path"],
            "evidence_paths": item["evidence_paths"],
        }
        for item in record_items
        if item["status"] == "failed" and item["blocking"]
    ]
    advisories = _advisories_for_records(record_items)
    metadata = verdict.metadata if isinstance(verdict.metadata, dict) else {}
    requested_profile = str(metadata.get("requested_profile", verdict.profile))
    selected_profile = verdict.profile
    execution = metadata.get("execution", {})
    changed_files = _string_list(metadata.get("changed_files"))
    changed_areas = _string_list(metadata.get("changed_areas"))
    return {
        "schema_version": VERDICT_SCHEMA_VERSION,
        "verdict_contract": verdict.verdict_contract,
        "ok": verdict.ok,
        "summary": verdict.summary,
        "profile": {
            "requested": requested_profile,
            "selected": selected_profile,
            "used": verdict.profile,
            "adaptive_requested": requested_profile == "adaptive",
            "adaptive_resolved": requested_profile == "adaptive" and selected_profile != "adaptive",
            "adaptive_reason": str(metadata.get("adaptive_reason", "")),
            "notes": verdict.profile_notes,
        },
        "merge_truth": verdict.merge_truth,
        "confidence": verdict.confidence_level,
        "recommendation": verdict.recommendation,
        "targeting": {
            "modes": check_summary["target_modes"],
            "used_targeted_execution": bool(check_summary["target_modes"].get("targeted", 0)),
            "used_smoke_execution": bool(check_summary["target_modes"].get("smoke", 0)),
            "used_full_execution": bool(check_summary["target_modes"].get("full", 0)),
        },
        "cache": {
            "enabled": bool(metadata.get("cache_enabled", False)),
            "summary": check_summary["cache_status"],
            "used_cache_hits": bool(check_summary["cache_status"].get("hit", 0)),
        },
        "execution": {
            "mode": execution.get("mode", "sequential")
            if isinstance(execution, dict)
            else "sequential",
            "workers": execution.get("workers", 1) if isinstance(execution, dict) else 1,
            "checks_recorded": int(metadata.get("checks_recorded", len(record_items))),
            "source": str(metadata.get("source", "")),
        },
        "changed_files": changed_files,
        "changed_areas": changed_areas,
        "changed_file_evidence_present": bool(changed_files),
        "check_results_summary": check_summary,
        "blockers": blockers,
        "advisories": advisories,
        "checks_run": [item for item in record_items if item["status"] != "skipped"],
        "checks_skipped": [item for item in record_items if item["status"] == "skipped"],
        "artifact_paths": artifact_paths,
    }


def build_fix_plan_payload(verdict_payload: dict[str, Any]) -> dict[str, Any]:
    auto_fixable: list[dict[str, Any]] = []
    manual_fixes: list[dict[str, Any]] = []
    follow_up_checks: list[dict[str, Any]] = []
    all_items = verdict_payload["checks_run"] + verdict_payload["checks_skipped"]
    for item in all_items:
        if item["status"] == "passed":
            continue
        issue = {
            "issue_id": f"{item['id']}:{item['status']}",
            "check_id": item["id"],
            "title": item["title"],
            "category": item["category"],
            "severity": _severity_for_record(item),
            "blocking": bool(item["blocking"]),
            "status": item["status"],
            "target_mode": item["target_mode"],
            "suggested_action": _suggested_action(item),
            "related_files": item["related_files"],
            "recommended_owner": _owner_for_category(item["category"]),
            "reason": item["reason"]
            or ("advisory finding" if not item["blocking"] else "failed check"),
        }
        if item["status"] == "failed" and _is_auto_fixable(item):
            auto_fixable.append(issue)
        else:
            manual_fixes.append(issue)
        follow_up_checks.append(
            {
                "check_id": item["id"],
                "category": item["category"],
                "target_mode": "full" if item["target_mode"] != "full" else item["target_mode"],
                "why": _follow_up_reason(item, verdict_payload),
            }
        )
    auto_fixable.sort(key=_issue_sort_key)
    manual_fixes.sort(key=_issue_sort_key)
    follow_up_checks.sort(key=lambda item: (item["check_id"], item["target_mode"], item["why"]))
    return {
        "schema_version": FIX_PLAN_SCHEMA_VERSION,
        "profile": verdict_payload["profile"],
        "confidence": verdict_payload["confidence"],
        "recommendation": verdict_payload["recommendation"],
        "targeting": verdict_payload["targeting"],
        "cache": verdict_payload["cache"],
        "summary": {
            "auto_fixable_candidates": len(auto_fixable),
            "manual_fixes": len(manual_fixes),
            "follow_up_checks": len(follow_up_checks),
        },
        "auto_fixable_candidates": auto_fixable,
        "manual_fixes": manual_fixes,
        "follow_up_checks": follow_up_checks,
    }


def build_risk_summary_payload(
    verdict_payload: dict[str, Any], fix_plan: dict[str, Any]
) -> dict[str, Any]:
    issues = fix_plan["auto_fixable_candidates"] + fix_plan["manual_fixes"]
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    by_category: dict[str, dict[str, Any]] = {}
    hotspots: dict[str, int] = {}
    for issue in issues:
        severity_counts[issue["severity"]] += 1
        category = issue["category"]
        entry = by_category.setdefault(
            category,
            {"category": category, "count": 0, "blocking": 0, "top_severity": "low"},
        )
        entry["count"] += 1
        if issue["blocking"]:
            entry["blocking"] += 1
        if _SEVERITY_ORDER[issue["severity"]] > _SEVERITY_ORDER[entry["top_severity"]]:
            entry["top_severity"] = issue["severity"]
        for path in issue["related_files"]:
            hotspots[path] = hotspots.get(path, 0) + 1
    for path in verdict_payload.get("changed_files", []):
        hotspots[path] = hotspots.get(path, 0) + 1
    hotspot_items = [
        {"path": path, "count": count}
        for path, count in sorted(hotspots.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "schema_version": RISK_SUMMARY_SCHEMA_VERSION,
        "profile": verdict_payload["profile"],
        "confidence": verdict_payload["confidence"],
        "merge_truth": verdict_payload["merge_truth"],
        "execution_truth": {
            "used_full_truth": verdict_payload["merge_truth"]
            and not verdict_payload["targeting"]["used_smoke_execution"]
            and not verdict_payload["targeting"]["used_targeted_execution"],
            "used_smoke_execution": verdict_payload["targeting"]["used_smoke_execution"],
            "used_targeted_execution": verdict_payload["targeting"]["used_targeted_execution"],
            "used_cache_hits": verdict_payload["cache"]["used_cache_hits"],
        },
        "severity_counts": severity_counts,
        "risk_by_category": sorted(
            by_category.values(),
            key=lambda item: (
                -item["blocking"],
                -_SEVERITY_ORDER[item["top_severity"]],
                item["category"],
            ),
        ),
        "top_blockers": verdict_payload["blockers"][:5],
        "risk_hotspots": hotspot_items[:10],
        "recommendation": verdict_payload["recommendation"],
        "check_results_summary": verdict_payload["check_results_summary"],
    }


def build_summary_markdown(verdict_payload: dict[str, Any], fix_plan: dict[str, Any]) -> str:
    profile = verdict_payload["profile"]
    summary = verdict_payload["check_results_summary"]
    blockers = verdict_payload["blockers"]
    advisories = verdict_payload["advisories"]
    next_actions = (fix_plan["auto_fixable_candidates"] + fix_plan["manual_fixes"])[:3]
    lines = [
        "# Validation Summary",
        "",
        f"- **Overall verdict:** {'PASS' if verdict_payload['ok'] else 'FAIL'}",
        f"- **Confidence:** {verdict_payload['confidence']}",
        f"- **Recommendation:** `{verdict_payload['recommendation']}`",
        f"- **Profile used:** requested `{profile['requested']}`, selected `{profile['selected']}`",
        f"- **Merge/release truth:** {'yes' if verdict_payload['merge_truth'] else 'no'}",
    ]
    if profile["adaptive_requested"]:
        lines.append(
            f"- **Adaptive resolution:** {profile['adaptive_reason'] or 'adaptive requested'}"
        )
    if verdict_payload["targeting"]["used_smoke_execution"]:
        lines.append(
            "- **Execution honesty:** smoke checks were used; this is not full verification."
        )
    if verdict_payload["targeting"]["used_targeted_execution"]:
        lines.append("- **Execution honesty:** targeted execution was used for part of this run.")
    if verdict_payload["cache"]["used_cache_hits"]:
        lines.append("- **Cache honesty:** cached check results were reused where safe.")
    lines.extend(
        [
            "",
            "## Checks",
            f"- Ran: {summary['run']} (`passed={summary['passed']}`, `failed={summary['failed']}`)",
            f"- Skipped: {summary['skipped']}",
            f"- Target modes: full={summary['target_modes']['full']}, smoke={summary['target_modes']['smoke']}, targeted={summary['target_modes']['targeted']}",
            f"- Cache: hit={summary['cache_status']['hit']}, fresh={summary['cache_status']['fresh']}, not-applicable={summary['cache_status']['not-applicable']}",
        ]
    )
    if blockers:
        lines.extend(["", "## Blockers"])
        for item in blockers[:5]:
            lines.append(
                f"- `{item['check_id']}` ({item['category']}, {item['severity']}): {item['reason']}"
            )
    else:
        lines.extend(["", "## Blockers", "- None"])
    if advisories:
        lines.extend(["", "## Advisories"])
        for item in advisories[:5]:
            lines.append(f"- `{item['check_id']}`: {item['message']}")
    else:
        lines.extend(["", "## Advisories", "- None"])
    lines.extend(["", "## Top next actions"])
    if next_actions:
        for item in next_actions:
            lines.append(f"- `{item['check_id']}` ({item['severity']}): {item['suggested_action']}")
    else:
        lines.append("- No follow-up actions required.")
    return "\n".join(lines) + "\n"


def write_evidence_zip(
    *,
    repo_root: Path,
    out_dir: Path,
    paths: ArtifactPaths,
    verdict_payload: dict[str, Any],
    fix_plan: dict[str, Any],
    risk_summary: dict[str, Any],
    summary_md: str,
    run_report_payload: dict[str, Any],
    records: tuple[CheckRecord, ...] | list[CheckRecord],
) -> None:
    zip_entries: list[tuple[str, bytes, str, str]] = [
        ("manifest.json", b"", "manifest", ""),
        (
            "verdict.json",
            _stable_json(verdict_payload).encode("utf-8"),
            "artifact",
            str(paths.verdict_json),
        ),
        ("summary.md", summary_md.encode("utf-8"), "artifact", str(paths.summary_md)),
        (
            "fix-plan.json",
            _stable_json(fix_plan).encode("utf-8"),
            "artifact",
            str(paths.fix_plan_json),
        ),
        (
            "risk-summary.json",
            _stable_json(risk_summary).encode("utf-8"),
            "artifact",
            str(paths.risk_summary_json),
        ),
        (
            "run-report.json",
            _stable_json(run_report_payload).encode("utf-8"),
            "artifact",
            str(paths.run_report_json),
        ),
    ]
    seen_sources: set[str] = set()
    for record in records:
        for rel in [record.log_path, *record.evidence_paths]:
            if not rel or rel in seen_sources:
                continue
            seen_sources.add(rel)
            source = repo_root / rel
            if not source.is_file():
                continue
            if _exclude_from_evidence(source, out_dir):
                continue
            arcname = (
                f"raw/{source.relative_to(out_dir).as_posix()}"
                if _is_relative_to(source, out_dir)
                else f"repo/{source.relative_to(repo_root).as_posix()}"
            )
            zip_entries.append((arcname, source.read_bytes(), "raw-evidence", str(source)))
    zip_entries.sort(key=lambda item: item[0])
    manifest = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "profile": verdict_payload["profile"],
        "recommendation": verdict_payload["recommendation"],
        "confidence": verdict_payload["confidence"],
        "contents": [
            {
                "path": arcname,
                "kind": kind,
                "source_path": source_path,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
            for arcname, payload, kind, source_path in zip_entries
            if arcname != "manifest.json"
        ],
        "excludes": ["cache/", ".venv/", ".pytest_cache/", ".ruff_cache/", "__pycache__/"],
    }
    zip_entries = [
        (
            "manifest.json",
            _stable_json(manifest).encode("utf-8"),
            "manifest",
            str(paths.evidence_zip.with_name("manifest.json")),
        ),
        *[item for item in zip_entries if item[0] != "manifest.json"],
    ]
    paths.evidence_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(paths.evidence_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for arcname, payload, _, _ in zip_entries:
            info = zipfile.ZipInfo(arcname)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload)


def serialize_record(record: CheckRecord) -> dict[str, Any]:
    metadata = record.metadata if isinstance(record.metadata, dict) else {}
    related_files = sorted(
        {
            *(_string_list(metadata.get("changed_paths"))),
            *(_string_list(metadata.get("selected_targets"))),
            *(str(path) for path in record.evidence_paths),
        }
    )
    return {
        "id": record.id,
        "title": record.title,
        "status": record.status,
        "blocking": record.blocking,
        "reason": record.reason,
        "command": record.command,
        "category": str(metadata.get("category", "uncategorized")),
        "truth_level": str(metadata.get("truth_level", "unknown")),
        "target_mode": str(metadata.get("target_mode", "full")),
        "target_reason": str(metadata.get("target_reason", "")),
        "cache_status": _cache_status(metadata),
        "log_path": record.log_path,
        "evidence_paths": sorted(record.evidence_paths),
        "elapsed_seconds": record.elapsed_seconds,
        "advisory": list(record.advisory),
        "related_files": related_files,
    }


def _check_results_summary(record_items: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "total": len(record_items),
        "run": 0,
        "skipped": 0,
        "passed": 0,
        "failed": 0,
        "blocking_failures": 0,
        "advisories": 0,
        "target_modes": {"full": 0, "smoke": 0, "targeted": 0},
        "cache_status": {"hit": 0, "fresh": 0, "not-applicable": 0},
    }
    target_modes = cast(dict[str, int], summary["target_modes"])
    cache_statuses = cast(dict[str, int], summary["cache_status"])
    for item in record_items:
        status = item["status"]
        if status == "skipped":
            summary["skipped"] += 1
        else:
            summary["run"] += 1
            summary[status] += 1
        if status == "failed" and item["blocking"]:
            summary["blocking_failures"] += 1
        summary["advisories"] += len(item["advisory"])
        target_mode = item["target_mode"] if item["target_mode"] in target_modes else "full"
        target_modes[target_mode] += 1
        cache_status = item["cache_status"]
        if cache_status not in cache_statuses:
            cache_status = "not-applicable"
        cache_statuses[cache_status] += 1
    return summary


def _advisories_for_records(record_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    advisories: list[dict[str, Any]] = []
    for item in record_items:
        for advisory in item["advisory"]:
            advisories.append(
                {
                    "check_id": item["id"],
                    "title": item["title"],
                    "category": item["category"],
                    "message": advisory,
                    "blocking": item["blocking"],
                }
            )
        if item["status"] == "skipped" and item["reason"]:
            advisories.append(
                {
                    "check_id": item["id"],
                    "title": item["title"],
                    "category": item["category"],
                    "message": item["reason"],
                    "blocking": item["blocking"],
                }
            )
    return advisories


def _severity_for_record(item: dict[str, Any]) -> str:
    if item["category"] == "security":
        return "high" if item["blocking"] else "medium"
    if item["status"] == "failed" and item["blocking"]:
        return "high" if item["target_mode"] == "full" else "medium"
    if item["status"] == "failed":
        return "low"
    if item["status"] == "skipped" and item["blocking"]:
        return "medium"
    return "low"


def _suggested_action(item: dict[str, Any]) -> str:
    return _ACTION_HINTS.get(
        item["id"],
        f"Investigate the `{item['id']}` {item['category']} result and re-run the affected lane.",
    )


def _follow_up_reason(item: dict[str, Any], verdict_payload: dict[str, Any]) -> str:
    if item["target_mode"] != "full":
        return "Run the full truth path before merge/release."
    if verdict_payload["cache"]["used_cache_hits"]:
        return "Re-run after remediation to refresh any cached evidence."
    return "Re-run after remediation to confirm the issue is resolved."


def _is_auto_fixable(item: dict[str, Any]) -> bool:
    return item["id"] in {"format_check", "lint"}


def _owner_for_category(category: str) -> str:
    return _OWNER_HINTS.get(category, "repository-maintainers")


def _issue_sort_key(item: dict[str, Any]) -> tuple[int, int, str, tuple[str, ...]]:
    return (
        -_SEVERITY_ORDER[item["severity"]],
        0 if item["blocking"] else 1,
        item["check_id"],
        tuple(item["related_files"]),
    )


def _exclude_from_evidence(path: Path, out_dir: Path) -> bool:
    parts = set(path.parts)
    if {"cache", ".venv", ".pytest_cache", ".ruff_cache", "__pycache__"} & parts:
        return True
    return _is_relative_to(path, out_dir / "cache")


def _cache_status(metadata: dict[str, Any]) -> str:
    cache = metadata.get("cache", {})
    if isinstance(cache, dict):
        return str(cache.get("status", "not-applicable"))
    return "not-applicable"


def _string_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    return []


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True
