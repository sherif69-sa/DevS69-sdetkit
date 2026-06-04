from __future__ import annotations

import re
from pathlib import Path


def test_operational_readiness_governance_workflow_uploads_expected_artifacts() -> None:
    workflow = Path(".github/workflows/operational-readiness-governance-contract.yml")
    text = workflow.read_text(encoding="utf-8")
    assert "name: operational-readiness-governance-contract" in text
    assert "make governance-contract-check" in text
    assert "actions/upload-artifact@" in text
    assert re.search(r"actions/upload-artifact@[0-9a-f]{40}", text)
    assert (
        "build/operational-readiness-governance/operational-readiness-governance-contract.json"
        in text
    )
    assert (
        "build/operational-readiness-governance/operational-readiness-release-evidence.json" in text
    )
    assert (
        "build/operational-readiness-governance/operational-readiness-release-evidence.md" in text
    )
    assert (
        "build/operational-readiness-governance/operational-readiness-governance-adherence.json"
        in text
    )
    assert (
        "build/operational-readiness-governance/operational-readiness-compliance-overlay-pack.json"
        in text
    )
    assert (
        "build/operational-readiness-governance/operational-readiness-policy-as-code-template.json"
        in text
    )
    assert (
        "build/operational-readiness-governance/operational-readiness-governance-drift-alerts.json"
        in text
    )
    assert (
        "build/operational-readiness-governance/operational-readiness-compliance-overlay-security.json"
        in text
    )
    assert (
        "build/operational-readiness-governance/operational-readiness-compliance-overlay-privacy.json"
        in text
    )
    assert (
        "build/operational-readiness-governance/operational-readiness-compliance-overlay-regulated.json"
        in text
    )
    assert "Validate exact artifact set" in text
    assert "operational-readiness-governance-drift-alerts.md" in text
    assert "expected = {" in text
    assert "artifact-set mismatch" in text


def test_operational_readiness_workflow_artifact_entries_are_unique() -> None:
    text = Path(".github/workflows/operational-readiness-governance-contract.yml").read_text(
        encoding="utf-8"
    )
    upload_section = text.split("path: |", 1)[1]
    expected = [
        "operational-readiness-governance-contract.json",
        "operational-readiness-release-evidence.json",
        "operational-readiness-release-evidence.md",
        "operational-readiness-governance-adherence.json",
        "operational-readiness-compliance-overlay-pack.json",
        "operational-readiness-policy-as-code-template.json",
        "operational-readiness-governance-drift-alerts.json",
        "operational-readiness-governance-drift-alerts.md",
        "operational-readiness-compliance-overlay-security.json",
        "operational-readiness-compliance-overlay-privacy.json",
        "operational-readiness-compliance-overlay-regulated.json",
    ]
    for name in expected:
        assert upload_section.count(name) == 1


def test_operational_readiness_workflow_is_repo_ci_only() -> None:
    text = Path(".github/workflows/operational-readiness-governance-contract.yml").read_text(
        encoding="utf-8"
    )
    assert "workflow_dispatch" not in text
    assert "pull_request:" in text
    assert "branches: [ main ]" in text
    assert "config/operational-readiness_drift_scoring.json" in text
