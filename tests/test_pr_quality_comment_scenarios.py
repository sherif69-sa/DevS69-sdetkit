from __future__ import annotations

import pytest

from sdetkit import pr_quality_action_report as report


def _scenario_model(
    state: str,
    *,
    risk_surface: str = "diagnostic_engine",
    security_findings: list[dict] | None = None,
    proof_commands: list[str] | None = None,
) -> dict:
    decision_by_state = {
        "waiting": (
            "none",
            "wait_for_required_checks",
            "wait_for_required_checks",
        ),
        "blocked": (
            "Ruff lint failed",
            "fix_lint",
            "do_not_merge_until_blocker_resolved",
        ),
        "review": (
            "none",
            "review_listed_evidence",
            "human_review_required_before_merge",
        ),
        "ready": (
            "none",
            "review_and_decide",
            "automated_proof_complete_human_decision_required",
        ),
        "stale": (
            "Evidence is stale for the current PR head",
            report.WAIT_FOR_CODE_SCANNING_REFRESH,
            report.WAIT_FOR_CODE_SCANNING_REFRESH,
        ),
        "invalid": (
            "PR Quality review evidence is internally inconsistent",
            "repair_review_evidence",
            "do_not_merge_until_review_model_repaired",
        ),
    }
    primary_blocker, next_action, merge_assessment = decision_by_state[state]

    failed = 1 if state in {"blocked", "invalid"} else 0
    queued = 1 if state == "waiting" else 0
    stale_alerts = 1 if state == "stale" else 0
    findings = security_findings or []

    return {
        "decision": {
            "review_state": state,
            "status": "green" if state in {"ready", "review", "stale"} else "failed",
            "source_status": "green" if state in {"ready", "review", "stale"} else "failed",
            "primary_blocker": primary_blocker,
            "merge_assessment": merge_assessment,
            "next_action": next_action,
            "risk_surface": risk_surface,
            "signal_title": "Scenario evidence changed",
            "comment_signal": "Evidence proof signal",
            "review_first_evidence": state == "review",
            "failed_checks": failed,
            "required_queued_checks": queued,
            "required_startup_failures": 0,
            "missing_required_contexts": 0,
            "cleared_security_signal": state == "stale",
            report.STALE_ONLY_SECURITY_SIGNAL: state == "stale",
        },
        "primary_blocker": {
            "title": primary_blocker,
            "surface": risk_surface,
            "action": next_action,
        },
        "recommended_actions": [],
        "failure_vector_signal": {
            "source": "scenario_fixture",
            "actual_failure": "F401 unused import" if failed else "none",
            "failure_type": "lint" if failed else "none",
            "failing_command": "python -m pre_commit run -a" if failed else "none",
            "failing_test_or_check": "ruff" if failed else "none",
            "owner_hint": "src/example.py" if failed else "none",
            "affected_files": ["src/example.py"] if failed else [],
            "safe_fix_candidate": False,
            "safe_fix_allowed": False,
            "reporting_only": True,
        },
        "ghas_blocker_details": {
            "collected": True,
            "collection_status": "collected",
            "open_alerts": len(findings) + stale_alerts,
            "current_alerts": len(findings),
            "stale_alerts": stale_alerts,
            "current_head_sha": "scenario-head",
            "dismissal_allowed": False,
            "findings": findings,
        },
        "failed_check_names": ["quality"] if failed else [],
        "required_queued_check_names": ["CI / Python 3.13"] if queued else [],
        "required_startup_failure_names": [],
        "missing_required_context_names": [],
        "proof_to_rerun": proof_commands or ["python -m pre_commit run -a"],
        "authority_boundary": {
            "boundary_mode": "reporting_only",
            "patch_automation": False,
            "security_dismissal": False,
            "merge_authorization": False,
            "semantic_equivalence_claim": False,
        },
    }


@pytest.mark.parametrize(
    ("state", "expected_command"),
    [
        ("waiting", "/check"),
        ("blocked", "/doctor"),
        ("review", "/hint"),
        ("ready", "/quality"),
        ("stale", "/check"),
        ("invalid", "/doctor"),
    ],
)
def test_quick_actions_prioritize_the_current_review_state(
    state: str,
    expected_command: str,
) -> None:
    summary = report.render_pr_quality_review_summary(_scenario_model(state))
    quick_actions = summary[
        summary.index("### Quick actions") : summary.index(
            "<summary>🧾 Machine decision contract</summary>"
        )
    ]

    assert f"**Recommended command:** `{expected_command}`" in quick_actions
    assert "<summary>More bot commands</summary>" in quick_actions
    assert quick_actions.count("**Recommended command:**") == 1


def test_first_screen_humanizes_risk_surface_but_retains_raw_contract() -> None:
    summary = report.render_pr_quality_review_summary(
        _scenario_model("ready", risk_surface="diagnostic_engine")
    )
    first_screen = summary.split(
        "<summary>🧾 Machine decision contract</summary>",
        maxsplit=1,
    )[0]

    assert "**Diagnostic engine**" in first_screen
    assert "`diagnostic_engine`" not in first_screen
    assert "| Risk surface | `diagnostic_engine` |" in summary


def test_blocked_comment_keeps_decision_failure_and_proof_visible() -> None:
    summary = report.render_pr_quality_review_summary(_scenario_model("blocked"))

    assert ("<details open>\n<summary>🚨 Active blocker / decision details</summary>") in summary
    assert ("<details open>\n<summary>🧭 Failure vector deep dive</summary>") in summary
    assert ("<details open>\n<summary>🧪 Proof to rerun</summary>") in summary


def test_current_security_comment_keeps_ghas_details_visible() -> None:
    finding = {
        "number": "9001",
        "rule_id": "SEC_SECRET_PATTERN",
        "severity": "error",
        "location": "src/example.py:42",
        "freshness": "current",
        "message": "Potential hardcoded credential",
        "proof_commands": [
            "python -m sdetkit security check --root . --format json",
        ],
        "dismissal_allowed": False,
    }
    summary = report.render_pr_quality_review_summary(
        _scenario_model(
            "blocked",
            risk_surface="security",
            security_findings=[finding],
        )
    )

    assert ("<details open>\n<summary>🛡️ GHAS / CodeQL blocker details</summary>") in summary


def test_security_proof_commands_are_consolidated_and_deduplicated() -> None:
    command = "python -m sdetkit security check --root . --format json"
    pre_commit = "python -m pre_commit run -a"
    finding = {
        "number": "9001",
        "rule_id": "SEC_SECRET_PATTERN",
        "severity": "error",
        "location": "src/example.py:42",
        "freshness": "current",
        "message": "Potential hardcoded credential",
        "proof_commands": [command, pre_commit, command],
        "dismissal_allowed": False,
    }
    model = _scenario_model(
        "blocked",
        risk_surface="security",
        security_findings=[finding],
        proof_commands=[command, pre_commit, command],
    )

    summary = report.render_pr_quality_review_summary(model)
    bash_blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in summary.splitlines():
        if line == "```bash":
            current = []
            continue
        if line == "```" and current is not None:
            bash_blocks.append(current)
            current = None
            continue
        if current is not None and line:
            current.append(line)

    commands = [item for block in bash_blocks for item in block]

    assert commands.count(command) == 1
    assert commands.count(pre_commit) == 1
    assert "Verification commands are consolidated in the Proof to rerun section." in summary


@pytest.mark.parametrize(
    "state",
    ["waiting", "blocked", "review", "ready", "stale", "invalid"],
)
def test_all_scenarios_preserve_reporting_only_authority(state: str) -> None:
    summary = report.render_pr_quality_review_summary(_scenario_model(state))

    assert "| Boundary mode | `reporting_only` |" in summary
    assert "| Patch automation | `false` |" in summary
    assert "| Security dismissal | `false` |" in summary
    assert "| Merge authorization | `false` |" in summary
    assert "| Semantic equivalence claim | `false` |" in summary
