from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "dependency-radar-bot.yml"
SCRIPT = ROOT / "scripts" / "build_dependency_radar_policy.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("build_dependency_radar_policy", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_zero_actionable_dependency_run_is_artifact_only() -> None:
    module = _load_script()
    policy, markdown = module.build_policy_and_markdown(
        {
            "packages": [],
            "summary": {
                "packages_audited": 0,
                "actionable_packages": 0,
                "max_risk_score": 0,
            },
        },
        runtime_fast_follow="# Runtime watchlist\n",
        repo_root=ROOT,
    )

    assert policy["actionable"] is False
    assert policy["actionable_package_count"] == 0
    assert policy["zero_finding_issue_creation"] is False
    assert policy["actionable_reasons"] == []
    assert "No issue is created when the audit reports zero actionable packages." in markdown


def test_dependency_radar_fails_closed_on_malformed_audit_evidence() -> None:
    module = _load_script()
    policy, _markdown = module.build_policy_and_markdown(
        {},
        runtime_fast_follow="",
        repo_root=ROOT,
    )

    assert policy["actionable"] is True
    assert policy["evidence_available"] is False
    assert policy["actionable_count_valid"] is False
    assert policy["actionable_reasons"] == [
        "dependency audit evidence unavailable or malformed",
        "actionable package count unavailable or malformed",
    ]


def test_positive_actionable_count_requires_dependency_follow_up() -> None:
    module = _load_script()
    policy, markdown = module.build_policy_and_markdown(
        {
            "packages": [{"name": "example", "validation_commands": ["pytest -q"]}],
            "summary": {"packages_audited": 1, "actionable_packages": 1},
        },
        runtime_fast_follow="",
        repo_root=ROOT,
    )

    assert policy["actionable"] is True
    assert policy["actionable_package_count"] == 1
    assert policy["actionable_reasons"] == ["actionable dependency packages: 1"]
    assert "A single rolling tracker is created or refreshed" in markdown


def test_workflow_uses_one_bot_managed_tracker_and_stays_below_heavy_budget() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    healthy_guard = "if (!actionable) {"
    create_call = "await github.rest.issues.create({"

    assert len(workflow.splitlines()) < 250
    assert "python scripts/build_dependency_radar_policy.py" in workflow
    assert "ACTIONABLE: ${{ steps.radar.outputs.actionable }}" in workflow
    assert "const rollingTitle = '📡 Dependency radar follow-up';" in workflow
    assert (
        "const generatedBodyMarker = '<!-- sdetkit:dependency-radar-tracker:v1 -->';"
        in workflow
    )
    assert "issue.user?.login === 'github-actions[bot]'" in workflow
    assert "issue.title.startsWith('📡 Dependency radar + runtime watchlist')" in workflow
    assert "state_reason: 'completed'" in workflow
    assert "const weekOf" not in workflow
    assert healthy_guard in workflow
    assert "return;" in workflow[workflow.index(healthy_guard) : workflow.rindex(create_call)]
    assert workflow.index(healthy_guard) < workflow.rindex(create_call)
