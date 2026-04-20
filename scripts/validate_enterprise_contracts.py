#!/usr/bin/env python3
"""Validate enterprise contract JSON files and adaptive sample artifacts.

Unlike fixed-date checks, this validator discovers the latest sample artifact per
family so the workflow stays active as new snapshots are produced.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

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
            _load_json(p)
        except Exception as exc:  # pragma: no cover - defensive branch
            errors.append(f"invalid json in {rel}: {exc}")
    return errors


def _latest_sample(prefix: str) -> Path | None:
    candidates = sorted((ROOT / "docs/artifacts").glob(f"{prefix}*.json"))
    return candidates[-1] if candidates else None


def _validate_sample_families() -> list[str]:
    errors: list[str] = []
    for prefix, expected_schema in SAMPLE_FAMILIES.items():
        p = _latest_sample(prefix)
        if p is None:
            errors.append(f"missing sample artifact family: docs/artifacts/{prefix}*.json")
            continue
        try:
            payload = _load_json(p)
        except Exception as exc:  # pragma: no cover - defensive branch
            errors.append(f"invalid json in {p.relative_to(ROOT)}: {exc}")
            continue

        if not isinstance(payload, dict):
            errors.append(f"unexpected payload type in {p.relative_to(ROOT)}")
            continue

        actual = payload.get("schema_version")
        if actual != expected_schema:
            errors.append(
                f"schema_version mismatch for {p.relative_to(ROOT)}: {actual!r} != {expected_schema!r}"
            )
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
