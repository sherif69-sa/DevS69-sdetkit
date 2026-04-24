#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must be a JSON object")
    return payload


def _load_upgrade_audit_payload(path: Path | None) -> dict[str, Any]:
    if path is not None:
        return _read_json(path)
    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit.upgrade_audit", "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"upgrade audit failed: exit={proc.returncode}, stderr={proc.stderr.strip()}"
        )
    payload = json.loads(proc.stdout)
    if not isinstance(payload, dict):
        raise ValueError("upgrade audit stdout must be JSON object")
    return payload


def _evaluate(summary: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    thresholds = policy.get("thresholds", {}) if isinstance(policy, dict) else {}
    if not isinstance(thresholds, dict):
        thresholds = {}
    max_critical = int(thresholds.get("critical_upgrade_signals_max", 0))
    max_high = int(thresholds.get("high_priority_upgrade_signals_max", 2))
    max_actionable = int(thresholds.get("actionable_packages_max", 12))

    critical = int(summary.get("critical_upgrade_signals", 0))
    high = int(summary.get("high_priority_upgrade_signals", 0))
    actionable = int(summary.get("actionable_packages", 0))

    breach_reasons: list[str] = []
    if critical > max_critical:
        breach_reasons.append(f"critical_upgrade_signals={critical} > max={max_critical}")
    if high > max_high:
        breach_reasons.append(f"high_priority_upgrade_signals={high} > max={max_high}")
    if actionable > max_actionable:
        breach_reasons.append(f"actionable_packages={actionable} > max={max_actionable}")

    return {
        "breach": bool(breach_reasons),
        "reasons": breach_reasons,
        "thresholds": {
            "critical_upgrade_signals_max": max_critical,
            "high_priority_upgrade_signals_max": max_high,
            "actionable_packages_max": max_actionable,
        },
    }


def build_radar(*, audit_payload: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    summary = audit_payload.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    evaluated = _evaluate(summary, policy)
    return {
        "schema_version": "sdetkit.phase3-dependency-radar.v1",
        "summary": summary,
        "policy": policy,
        "threshold_check": evaluated,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build phase-3 dependency radar artifact with threshold checks."
    )
    parser.add_argument(
        "--audit-json", type=Path, default=None, help="Optional prebuilt upgrade audit JSON."
    )
    parser.add_argument(
        "--policy-json",
        type=Path,
        default=Path("config/dependency_slo_policy.json"),
        help="Dependency SLO policy JSON path.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/artifacts/phase3-dependency-radar-2026-04-24.json"),
    )
    parser.add_argument("--fail-on-breach", action="store_true")
    args = parser.parse_args(argv)

    audit_payload = _load_upgrade_audit_payload(args.audit_json)
    policy = _read_json(args.policy_json)
    radar = build_radar(audit_payload=audit_payload, policy=policy)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(radar, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"ok": True, "out": args.out.as_posix(), "breach": radar["threshold_check"]["breach"]}
        )
    )
    if args.fail_on_breach and bool(radar["threshold_check"]["breach"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
