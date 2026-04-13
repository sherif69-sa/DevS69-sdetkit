from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor, review
from sdetkit.checks import artifacts as check_artifacts


def test_artifact_contract_index_schema_versions_are_in_sync() -> None:
    payload = json.loads(Path("docs/artifact-contract-index.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sdetkit.artifact-contract-index.v1"

    entries = {item["id"]: item for item in payload["artifacts"]}
    assert entries["doctor-json"]["schema_version"] == doctor.SCHEMA_VERSION
    assert entries["review-json"]["schema_version"] == review.SCHEMA_VERSION
    assert entries["checks-verdict-json"]["schema_version"] == check_artifacts.VERDICT_SCHEMA_VERSION
    assert entries["checks-fix-plan-json"]["schema_version"] == check_artifacts.FIX_PLAN_SCHEMA_VERSION
    assert (
        entries["checks-risk-summary-json"]["schema_version"]
        == check_artifacts.RISK_SUMMARY_SCHEMA_VERSION
    )
    assert entries["checks-evidence-zip"]["schema_version"] == check_artifacts.EVIDENCE_SCHEMA_VERSION


def test_artifact_contract_index_includes_canonical_gate_artifacts() -> None:
    payload = json.loads(Path("docs/artifact-contract-index.json").read_text(encoding="utf-8"))
    entries = {item["id"]: item for item in payload["artifacts"]}

    for artifact_id in ("gate-fast-json", "release-preflight-json"):
        assert artifact_id in entries
        required = set(entries[artifact_id]["required_fields"])
        assert {"ok", "failed_steps", "profile"}.issubset(required)
