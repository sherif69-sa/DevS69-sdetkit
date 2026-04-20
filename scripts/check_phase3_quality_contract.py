#!/usr/bin/env python3
"""Validate Phase 3 quality-engine contract artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.phase3_quality_engine import (
    build_adaptive_planning,
    build_next_pass_handoff,
    build_remediation_v2,
    build_trend_delta,
    load_json,
    validate_phase3_payloads,
)


def _load_changed_paths(path: Path | None) -> list[str]:
    if path is None or not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _emit_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_previous_summary(explicit: str | None, current_summary: Path) -> Path | None:
    if explicit:
        return Path(explicit)
    history_dir = current_summary.parent / "history"
    if history_dir.is_dir():
        candidates = sorted(
            path
            for path in history_dir.glob("*.json")
            if path.is_file() and path.resolve() != current_summary.resolve()
        )
        if candidates:
            return candidates[-1]
    return None


def _evaluate_check_matrix(
    failures: list[str], doctor_alignment_status: str
) -> list[dict[str, object]]:
    checks = [
        {
            "id": "adaptive_planning_schema",
            "ok": not any(item.startswith("adaptive ") for item in failures),
        },
        {
            "id": "remediation_v2_schema",
            "ok": not any(item.startswith("remediation_v2 ") for item in failures),
        },
        {
            "id": "trend_delta_schema",
            "ok": not any(item.startswith("trend ") for item in failures),
        },
        {
            "id": "next_pass_schema",
            "ok": not any(item.startswith("next_pass ") for item in failures),
        },
        {
            "id": "deterministic_ordering",
            "ok": not any("not deterministically sorted" in item for item in failures),
        },
        {
            "id": "next_pass_reason_code_contract",
            "ok": not any(
                "next_pass recommendation reason_code missing" in item for item in failures
            ),
        },
    ]
    checks.append(
        {
            "id": "doctor_handoff_alignment",
            "ok": doctor_alignment_status in {"aligned", "no-doctor"},
        }
    )
    return checks


def _doctor_handoff_alignment(doctor_summary: dict[str, Any], next_pass: dict[str, Any]) -> str:
    enterprise = doctor_summary.get("enterprise", {})
    if not isinstance(enterprise, dict):
        return "no-doctor"
    doctor_reason = str(enterprise.get("next_pass_reason", "")).strip()
    if not doctor_reason:
        return "no-doctor"
    recommendations = next_pass.get("recommendations", [])
    first_reason = ""
    if isinstance(recommendations, list) and recommendations:
        first = recommendations[0]
        if isinstance(first, dict):
            first_reason = str(first.get("reason_code", "")).strip()
    if doctor_reason == "none":
        return "aligned" if not first_reason or first_reason == "check_recovered" else "mismatch"
    if doctor_reason == "blockers_present":
        return (
            "aligned"
            if first_reason in {"critical_required_check_failed", "required_check_failed"}
            else "mismatch"
        )
    if doctor_reason == "failed_checks_present":
        return (
            "aligned"
            if first_reason in {"required_check_failed", "optional_check_failed"}
            else "mismatch"
        )
    return "no-doctor"


def _doctor_handoff_alignment_reason(status: str, doctor_summary: dict[str, Any]) -> str:
    if status == "aligned":
        return "doctor_next_pass_consistent"
    if status == "mismatch":
        return "doctor_next_pass_conflicts_with_phase3_recommendation"
    enterprise = doctor_summary.get("enterprise", {})
    if isinstance(enterprise, dict) and str(enterprise.get("next_pass_reason", "")).strip():
        return "doctor_next_pass_reason_unrecognized"
    return "doctor_next_pass_unavailable"


def _summarize_checks_by_lane(checks: list[dict[str, object]]) -> dict[str, dict[str, int]]:
    lane_prefixes = {
        "adaptive": ("adaptive_",),
        "remediation": ("remediation_",),
        "trend": ("trend_",),
        "next_pass": ("next_pass_", "doctor_handoff_alignment"),
        "global": ("phase3_payload_contract", "summary_exists", "deterministic_ordering"),
    }
    out: dict[str, dict[str, int]] = {}
    for lane, prefixes in lane_prefixes.items():
        rows = [
            row
            for row in checks
            if isinstance(row, dict)
            and any(str(row.get("id", "")).startswith(prefix) for prefix in prefixes)
        ]
        total = len(rows)
        passed = sum(1 for row in rows if bool(row.get("ok")))
        out[lane] = {"total": total, "passed": passed, "failed": total - passed}
    return out


def _summarize_checks(checks: list[dict[str, object]]) -> dict[str, int]:
    total = len(checks)
    passed = sum(1 for row in checks if bool(row.get("ok")))
    failed = total - passed
    return {"total": total, "passed": passed, "failed": failed}


def _decision(
    *, failures: list[str], doctor_alignment_status: str, doctor_alignment_mode: str
) -> str:
    if failures:
        return "fail"
    if doctor_alignment_mode == "warn" and doctor_alignment_status == "mismatch":
        return "warn"
    return "pass"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="build/phase1-baseline/phase1-baseline-summary.json")
    parser.add_argument("--previous-summary", default=None)
    parser.add_argument(
        "--changed-paths", default=None, help="Optional newline-delimited changed paths file"
    )
    parser.add_argument(
        "--doctor-summary",
        default="build/phase1-baseline/doctor.json",
        help="Optional doctor summary for next-pass handoff alignment checks.",
    )
    parser.add_argument(
        "--doctor-alignment-mode",
        choices=["strict", "warn", "off"],
        default="strict",
        help="Whether doctor handoff mismatch should fail (strict), warn, or be ignored (off).",
    )
    parser.add_argument("--out-dir", default="build/phase3-quality")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    summary_path = Path(args.summary)
    previous_path = _resolve_previous_summary(args.previous_summary, summary_path)
    changed_paths_path = Path(args.changed_paths) if args.changed_paths else None
    doctor_summary_path = Path(args.doctor_summary) if args.doctor_summary else None
    out_dir = Path(args.out_dir)

    checks: list[dict[str, object]] = []
    failures: list[str] = []

    summary = load_json(summary_path)
    checks.append({"id": "summary_exists", "ok": bool(summary), "path": str(summary_path)})
    if not summary:
        failures.append(f"missing phase1 summary: {summary_path}")
        payload = {
            "ok": False,
            "schema_version": "sdetkit.phase3_quality_contract.v1",
            "checks": checks,
            "failures": failures,
            "doctor_handoff_alignment": "no-doctor",
            "doctor_handoff_alignment_reason": "doctor_next_pass_unavailable",
            "doctor_alignment_mode": args.doctor_alignment_mode,
            "summary": _summarize_checks(checks),
            "summary_by_lane": _summarize_checks_by_lane(checks),
            "decision": "fail",
        }
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("phase3-quality-contract: FAIL")
            print("- decision: fail")
            print("- doctor_handoff_alignment: no-doctor")
            print("- doctor_handoff_alignment_reason: doctor_next_pass_unavailable")
            for item in failures:
                print(f"- {item}")
        return 1

    summary["_source"] = str(summary_path)
    previous = load_json(previous_path) if previous_path else {}
    if previous and previous_path is not None:
        previous["_source"] = str(previous_path)

    adaptive = build_adaptive_planning(summary, _load_changed_paths(changed_paths_path))
    remediation = build_remediation_v2(summary, adaptive)
    trend = build_trend_delta(summary, previous or None)
    next_pass = build_next_pass_handoff(remediation, adaptive)
    doctor_summary = load_json(doctor_summary_path) if doctor_summary_path else {}
    doctor_alignment_status = _doctor_handoff_alignment(doctor_summary, next_pass)
    doctor_alignment_reason = _doctor_handoff_alignment_reason(
        doctor_alignment_status, doctor_summary
    )

    _emit_payload(out_dir / "phase3-adaptive-planning.json", adaptive)
    _emit_payload(out_dir / "phase3-remediation-v2.json", remediation)
    _emit_payload(out_dir / "phase3-trend-delta.json", trend)
    _emit_payload(out_dir / "phase3-next-pass-handoff.json", next_pass)

    failures.extend(validate_phase3_payloads(adaptive, remediation, trend, next_pass))
    checks.extend(_evaluate_check_matrix(failures, doctor_alignment_status))
    doctor_mismatch_is_failure = (
        args.doctor_alignment_mode == "strict" and doctor_alignment_status == "mismatch"
    )
    checks.append(
        {"id": "phase3_payload_contract", "ok": not failures and not doctor_mismatch_is_failure}
    )
    if doctor_mismatch_is_failure:
        failures.append("doctor handoff alignment mismatch")
    if args.doctor_alignment_mode == "warn" and doctor_alignment_status == "mismatch":
        checks.append({"id": "doctor_handoff_alignment_warning", "ok": True})

    payload = {
        "ok": not failures,
        "schema_version": "sdetkit.phase3_quality_contract.v1",
        "out_dir": str(out_dir),
        "checks": checks,
        "failures": failures,
        "doctor_handoff_alignment": doctor_alignment_status,
        "doctor_handoff_alignment_reason": doctor_alignment_reason,
        "doctor_alignment_mode": args.doctor_alignment_mode,
        "summary": _summarize_checks(checks),
        "summary_by_lane": _summarize_checks_by_lane(checks),
        "decision": _decision(
            failures=failures,
            doctor_alignment_status=doctor_alignment_status,
            doctor_alignment_mode=args.doctor_alignment_mode,
        ),
        "artifacts": {
            "adaptive_planning": str(out_dir / "phase3-adaptive-planning.json"),
            "remediation_v2": str(out_dir / "phase3-remediation-v2.json"),
            "trend_delta": str(out_dir / "phase3-trend-delta.json"),
            "next_pass_handoff": str(out_dir / "phase3-next-pass-handoff.json"),
        },
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("phase3-quality-contract: OK" if payload["ok"] else "phase3-quality-contract: FAIL")
        print(f"- decision: {payload['decision']}")
        print(f"- doctor_handoff_alignment: {payload['doctor_handoff_alignment']}")
        print(f"- doctor_handoff_alignment_reason: {payload['doctor_handoff_alignment_reason']}")
        for row in checks:
            print(f"[{'OK' if row['ok'] else 'FAIL'}] {row['id']}")
        for item in failures:
            print(f"- {item}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
