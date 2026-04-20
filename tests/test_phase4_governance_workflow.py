from __future__ import annotations

from pathlib import Path


def test_phase4_governance_workflow_uploads_expected_artifacts() -> None:
    workflow = Path('.github/workflows/phase4-governance-contract.yml')
    text = workflow.read_text(encoding='utf-8')
    assert 'name: phase4-governance-contract' in text
    assert 'make phase4-governance-contract' in text
    assert 'actions/upload-artifact@v4' in text
    assert 'build/phase4-governance/phase4-governance-contract.json' in text
    assert 'build/phase4-governance/phase4-release-evidence.json' in text
    assert 'build/phase4-governance/phase4-release-evidence.md' in text
    assert 'build/phase4-governance/phase4-governance-adherence.json' in text
    assert 'build/phase4-governance/phase4-compliance-overlay-pack.json' in text
    assert 'build/phase4-governance/phase4-policy-as-code-template.json' in text
    assert 'build/phase4-governance/phase4-governance-drift-alerts.json' in text
    assert 'build/phase4-governance/phase4-compliance-overlay-security.json' in text
    assert 'build/phase4-governance/phase4-compliance-overlay-privacy.json' in text
    assert 'build/phase4-governance/phase4-compliance-overlay-regulated.json' in text
    assert 'Validate exact artifact set' in text
    assert 'phase4-governance-drift-alerts.md' in text
    assert 'expected = {' in text
    assert 'artifact-set mismatch' in text


def test_phase4_workflow_artifact_entries_are_unique() -> None:
    text = Path('.github/workflows/phase4-governance-contract.yml').read_text(encoding='utf-8')
    upload_section = text.split('path: |', 1)[1]
    expected = [
        'phase4-governance-contract.json',
        'phase4-release-evidence.json',
        'phase4-release-evidence.md',
        'phase4-governance-adherence.json',
        'phase4-compliance-overlay-pack.json',
        'phase4-policy-as-code-template.json',
        'phase4-governance-drift-alerts.json',
        'phase4-governance-drift-alerts.md',
        'phase4-compliance-overlay-security.json',
        'phase4-compliance-overlay-privacy.json',
        'phase4-compliance-overlay-regulated.json',
    ]
    for name in expected:
        assert upload_section.count(name) == 1


def test_phase4_workflow_is_repo_ci_only() -> None:
    text = Path('.github/workflows/phase4-governance-contract.yml').read_text(encoding='utf-8')
    assert 'workflow_dispatch' not in text
    assert 'pull_request:' in text
    assert 'branches: [ main ]' in text
    assert "config/phase4_drift_scoring.json" in text
