#!/usr/bin/env python3
"""Validate enterprise contract JSON files and adaptive sample artifacts.

Unlike fixed-date checks, this validator discovers the latest sample artifact per
family so the workflow stays active as new snapshots are produced.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIO_DB_SCRIPT = ROOT / "scripts/build_adaptive_scenario_database.py"

CONTRACTS: tuple[str, ...] = (
    "docs/contracts/core-command-contract.v1.json",
    "docs/contracts/workflow-consolidation-plan.v1.json",
    "docs/contracts/enterprise-default-profile.v1.json",
    "docs/contracts/module-rationalization-plan.v1.json",
    "docs/contracts/ci-cost-telemetry.v1.json",
    "docs/contracts/toolkit-reliability-slo.v1.json",
    "docs/contracts/policy-control-catalog.v1.json",
    "docs/contracts/golden-template-catalog.v1.json",
    "docs/contracts/support-lifecycle-policy.v1.json",
    "docs/contracts/adaptive-postcheck-scenarios.v1.json",
)

SAMPLE_FAMILIES: dict[str, str] = {
    "ci-cost-telemetry-sample-": "sdetkit.ci-cost-telemetry.v1",
    "toolkit-reliability-snapshot-": "sdetkit.toolkit-reliability-snapshot.v1",
    "policy-control-catalog-sample-": "sdetkit.policy-control-catalog.v1",
    "golden-template-catalog-sample-": "sdetkit.golden-template-catalog.v1",
    "support-lifecycle-policy-sample-": "sdetkit.support-lifecycle-policy.v1",
    "adaptive-postcheck-": "sdetkit.adaptive-postcheck.v1",
    "adaptive-scenario-database-": "sdetkit.adaptive-scenario-database.v1",
}


def _load_json(path: Path) -> dict | list:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _validate_contracts() -> list[str]:
    errors: list[str] = []
    for rel in CONTRACTS:
        p = ROOT / rel
        if not p.exists():
            errors.append(f"missing contract: {rel}")
            continue
        try:
            payload = _load_json(p)
        except Exception as exc:  # pragma: no cover - defensive branch
            errors.append(f"invalid json in {rel}: {exc}")
            continue

        if rel.endswith("adaptive-postcheck-scenarios.v1.json") and isinstance(payload, dict):
            errors.extend(_validate_adaptive_postcheck_contract(payload, rel))
    return errors


def _validate_adaptive_postcheck_contract(payload: dict, rel: str) -> list[str]:
    errors: list[str] = []
    owner_routing = payload.get("owner_routing", {})
    if not isinstance(owner_routing, dict) or not owner_routing:
        errors.append(f"{rel}: owner_routing must be a non-empty object")
    else:
        for check_name, row in owner_routing.items():
            if not isinstance(check_name, str) or not isinstance(row, dict):
                errors.append(f"{rel}: owner_routing entries must map check-name -> object")
                continue
            for key in ("owner", "severity", "sla"):
                value = row.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{rel}: owner_routing[{check_name!r}].{key} must be a non-empty string")

    scenarios = payload.get("scenarios", {})
    if not isinstance(scenarios, dict):
        return [f"{rel}: scenarios must be an object"]

    required_profiles = ("fast", "balanced", "strict")
    required_checks = {
        "pr_outcome_feedback_present",
        "mistake_learning_signal_depth",
        "adaptive_learning_precision_ready",
    }
    required_minimums = (
        "minimum_pr_outcome_feedback",
        "minimum_mistake_learning_event",
        "minimum_learning_signal_total",
    )

    for profile in required_profiles:
        row = scenarios.get(profile)
        if not isinstance(row, dict):
            errors.append(f"{rel}: missing scenario profile {profile!r}")
            continue

        enabled = row.get("enabled_checks", [])
        if not isinstance(enabled, list):
            errors.append(f"{rel}: {profile}.enabled_checks must be a list")
            continue

        enabled_set = {str(x) for x in enabled}
        missing = sorted(required_checks - enabled_set)
        if missing:
            errors.append(f"{rel}: {profile} missing required checks: {', '.join(missing)}")

        for key in required_minimums:
            value = row.get(key)
            if not isinstance(value, int) or value <= 0:
                errors.append(f"{rel}: {profile}.{key} must be a positive integer")

    return errors


def _latest_sample(prefix: str) -> Path | None:
    candidates = sorted((ROOT / "docs/artifacts").glob(f"{prefix}*.json"))
    return candidates[-1] if candidates else None


def _fresh_adaptive_scenario_database_sample() -> dict | list | None:
    fd, path = tempfile.mkstemp(prefix="adaptive-scenario-database-", suffix=".json")
    os.close(fd)
    out_path = Path(path)
    try:
        result = subprocess.run(
            [sys.executable, str(SCENARIO_DB_SCRIPT), ".", "--out", str(out_path)],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
        )
        if result.returncode != 0:
            return None
        return _load_json(out_path)
    except Exception:  # pragma: no cover - defensive branch
        return None
    finally:
        try:
            out_path.unlink(missing_ok=True)
        except Exception:  # pragma: no cover - defensive branch
            pass


def _adaptive_scenario_sample_with_fallback() -> tuple[dict | list | None, Path, list[str]]:
    latest = _latest_sample("adaptive-scenario-database-")
    if latest is not None:
        try:
            rel = latest.relative_to(ROOT)
        except ValueError:
            rel = latest
        try:
            payload = _load_json(latest)
        except Exception as exc:  # pragma: no cover - defensive branch
            return None, rel, [f"invalid json in {rel}: {exc}"]
        if isinstance(payload, dict) and payload.get("schema_version") == "sdetkit.adaptive-scenario-database.v1":
            semantic_errors = _validate_adaptive_scenario_database_sample(payload, rel)
            if not semantic_errors:
                return payload, rel, []

    rel = Path("build/generated-adaptive-scenario-database.json")
    payload = _fresh_adaptive_scenario_database_sample()
    if payload is None:
        return None, rel, ["failed to build fresh adaptive scenario database sample"]
    return payload, rel, []


def _validate_sample_families() -> list[str]:
    errors: list[str] = []
    for prefix, expected_schema in SAMPLE_FAMILIES.items():
        rel = None
        if prefix == "adaptive-scenario-database-":
            payload, rel, prep_errors = _adaptive_scenario_sample_with_fallback()
            if prep_errors:
                errors.extend(prep_errors)
                continue
        else:
            p = _latest_sample(prefix)
            if p is None:
                errors.append(f"missing sample artifact family: docs/artifacts/{prefix}*.json")
                continue
            rel = p.relative_to(ROOT)
            try:
                payload = _load_json(p)
            except Exception as exc:  # pragma: no cover - defensive branch
                errors.append(f"invalid json in {rel}: {exc}")
                continue

        if not isinstance(payload, dict):
            errors.append(f"unexpected payload type in {rel}")
            continue

        actual = payload.get("schema_version")
        if actual != expected_schema:
            errors.append(
                f"schema_version mismatch for {rel}: {actual!r} != {expected_schema!r}"
            )
            continue

        if expected_schema == "sdetkit.adaptive-scenario-database.v1":
            errors.extend(_validate_adaptive_scenario_database_sample(payload, rel))
    return errors


def _validate_adaptive_scenario_database_sample(payload: dict, rel: Path) -> list[str]:
    errors: list[str] = []
    summary = payload.get("summary", {})
    if not isinstance(summary, dict):
        return [f"{rel}: summary must be an object"]
    kinds = summary.get("kinds", {})
    if not isinstance(kinds, dict):
        errors.append(f"{rel}: summary.kinds must be an object")
        return errors

    required_kinds = (
        "adaptive_pr_reviewer_matrix",
        "pr_outcome_feedback",
        "mistake_learning_event",
        "reviewer_agent_handoff",
    )
    for key in required_kinds:
        value = kinds.get(key)
        if not isinstance(value, int) or value <= 0:
            errors.append(f"{rel}: summary.kinds[{key!r}] must be a positive integer")

    adaptive_learning = summary.get("adaptive_learning", {})
    if not isinstance(adaptive_learning, dict):
        errors.append(f"{rel}: summary.adaptive_learning must be an object")
        return errors

    for key in ("pr_outcome_feedback", "mistake_learning_event", "learning_signal_total"):
        value = adaptive_learning.get(key)
        if not isinstance(value, int) or value < 0:
            errors.append(f"{rel}: summary.adaptive_learning.{key} must be a non-negative integer")

    coverage = adaptive_learning.get("learning_coverage_score")
    if not isinstance(coverage, int) or coverage < 0 or coverage > 100:
        errors.append(f"{rel}: summary.adaptive_learning.learning_coverage_score must be 0..100 int")

    precision_ready = adaptive_learning.get("precision_ready")
    if not isinstance(precision_ready, bool):
        errors.append(f"{rel}: summary.adaptive_learning.precision_ready must be boolean")

    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(_validate_contracts())
    errors.extend(_validate_sample_families())

    if errors:
        for e in errors:
            print(f"[enterprise-contracts-check] {e}")
        return 1

    print("[enterprise-contracts-check] OK: contracts valid and latest sample families aligned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
