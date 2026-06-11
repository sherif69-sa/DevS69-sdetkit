from __future__ import annotations

import json
from pathlib import Path

from sdetkit import check_intelligence
from sdetkit import pr_quality_action_report as report


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_action_report_green_comment_is_short_and_not_educational() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 12,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        evidence_narrative={"quality": {"ok": True, "coverage_percent": "96.69%"}},
    )

    assert "SDETKit Review Result: Green" in body
    assert "No action required from SDETKit." in body
    assert "Failed checks: `0`" in body
    assert "Unresolved security findings: `0`" in body
    assert "Why it matters" not in body
    assert "Quality is green, so the review focus is not coverage." not in body
    assert "The comment must guide maintainers" not in body


def test_action_report_review_required_comment_shows_real_blocker_and_fix_path() -> None:
    action = {
        "status": "review_required",
        "primary_blocker": {
            "check": "Fast CI lane py3.12",
            "title": "Ruff lint contract failed",
            "surface": "quality",
            "code": "RUFF_LINT_FAILURE",
            "impact": "CI is blocked by an unused local variable.",
            "path": "src/sdetkit/check_intelligence.py",
        },
        "automation": {
            "attempted": False,
            "allowed": False,
            "reason": "diagnosis is review-first or not approved for automatic mutation",
        },
        "recommended_actions": ["Remove the unused assignment and rerun Ruff."],
        "proof_commands": ["python -m ruff check src tests", "python -m pre_commit run -a"],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 4,
        "failed_checks": [
            {
                "name": "Fast CI lane py3.12",
                "safe_to_auto_fix": False,
                "diagnosis": {
                    "code": "RUFF_LINT_FAILURE",
                    "title": "Ruff lint contract failed",
                },
            }
        ],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }

    body = report.render_comment_body(action_report=action, check_intelligence=intelligence)

    assert "SDETKit Review Result: Action required" in body
    assert "Fast CI lane py3.12" in body
    assert "Ruff lint contract failed" in body
    assert "src/sdetkit/check_intelligence.py" in body
    assert "Remove the unused assignment" in body
    assert "python -m ruff check src tests" in body
    assert "Review the security evidence against the PR diff." not in body
    assert "Confirm the graph findings match the changed files and artifacts." not in body


def test_action_report_safe_fix_available_comment_preserves_no_auto_apply_boundary() -> None:
    action = {
        "status": "safe_fix_available",
        "primary_blocker": {
            "check": "ruff",
            "title": "Ruff fixable lint can be mechanically remediated",
            "surface": "quality",
            "code": "RUFF_FIXABLE_LINT",
            "impact": "A narrow import sorting issue is fixable by Ruff.",
        },
        "automation": {
            "attempted": False,
            "allowed": True,
            "reason": "diagnosis is approved for narrow mechanical safe-fix planning",
        },
        "recommended_actions": ["Run ruff check --fix on affected files."],
        "proof_commands": ["python -m ruff check src tests", "python -m pre_commit run -a"],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 1,
        "failed_checks": [
            {
                "name": "ruff",
                "safe_to_auto_fix": True,
                "diagnosis": {
                    "code": "RUFF_FIXABLE_LINT",
                    "title": "Ruff fixable lint can be mechanically remediated",
                },
            }
        ],
        "queued_checks": [],
        "startup_failures": [],
    }

    body = report.render_comment_body(action_report=action, check_intelligence=intelligence)

    assert "SDETKit Review Result: Safe fix available" in body
    assert "Allowed: `true`" in body
    assert "Attempted: `false`" in body
    assert "Run ruff check --fix on affected files." in body


def test_action_report_cli_writes_comment_body(tmp_path: Path, capsys) -> None:
    action_path = _write_json(
        tmp_path / "action-report.json",
        {
            "status": "green",
            "primary_blocker": {},
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": "no remediation needed",
            },
            "recommended_actions": [],
            "proof_commands": [],
        },
    )
    intelligence_path = _write_json(
        tmp_path / "check-intelligence.json",
        {
            "checks_seen": 1,
            "failed_checks": [],
            "queued_checks": [],
            "startup_failures": [],
            "security_review": {"collected": True, "unresolved_findings": 0},
        },
    )
    out = tmp_path / "comment.md"

    rc = report.main(
        [
            "--action-report",
            str(action_path),
            "--check-intelligence",
            str(intelligence_path),
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["out"] == out.as_posix()
    assert printed["status"] == "green"
    assert printed["result_title"] == "Green"
    assert printed["evidence_signal_kind"] == "none"
    assert printed["evidence_signal_present"] is False
    assert printed["evidence_review_required"] is False
    assert "SDETKit Review Result: Green" in out.read_text(encoding="utf-8")


def test_check_intelligence_promotes_unresolved_security_review_to_action_report() -> None:
    intelligence = {
        "checks_seen": 2,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {
            "collected": True,
            "unresolved_findings": 1,
            "findings": [
                {
                    "title": "Security review requires action in src/sdetkit/check_intelligence.py",
                    "summary": "CodeQL reported an unused local variable.",
                    "path": "src/sdetkit/check_intelligence.py",
                    "line": 314,
                    "comment_url": "https://example.test/security-comment",
                    "recommended_commands": ["python -m ruff check src tests"],
                }
            ],
        },
    }

    action = check_intelligence.build_action_report(intelligence)
    body = report.render_comment_body(action_report=action, check_intelligence=intelligence)

    assert action["status"] == "review_required"
    assert action["primary_blocker"]["surface"] == "security"
    assert action["primary_blocker"]["path"] == "src/sdetkit/check_intelligence.py"
    assert "Security review requires action" in body
    assert "src/sdetkit/check_intelligence.py:314" in body
    assert "CodeQL reported an unused local variable." in body
    assert "python -m ruff check src tests" in body


def test_action_report_green_comment_reports_optional_queued_without_blocking() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {
            "queued_check_count": 1,
            "required_queued_check_count": 0,
            "startup_failure_count": 0,
            "required_startup_failure_count": 0,
        },
    }
    intelligence = {
        "checks_seen": 42,
        "failed_checks": [],
        "queued_checks": [{"name": "Full CI lane", "status": "queued", "required": False}],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }

    body = report.render_comment_body(action_report=action, check_intelligence=intelligence)

    assert "SDETKit Review Result: Green" in body
    assert "Queued checks: `1`" in body
    assert "Required queued checks: `0`" in body
    assert "Primary blocker" in body
    assert "- none" in body
    assert "Checks are not complete" not in body


def test_action_report_incomplete_comment_shows_missing_required_context() -> None:
    action = {
        "status": "incomplete",
        "primary_blocker": {
            "check": "ci",
            "title": "Required checks are not complete",
            "surface": "workflow",
            "code": "CHECKS_INCOMPLETE",
            "impact": "Required context has not reported yet.",
        },
        "automation": {
            "attempted": False,
            "allowed": False,
            "reason": "required check completion is needed before remediation or green signoff",
        },
        "recommended_actions": ["Wait for required queued checks to complete."],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 2,
        "missing_required_contexts": ["ci"],
        "failed_checks": [],
        "queued_checks": [
            {
                "name": "ci",
                "status": "queued",
                "required": True,
                "missing_required_context": True,
            }
        ],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }

    body = report.render_comment_body(action_report=action, check_intelligence=intelligence)

    assert "SDETKit Review Result: Checks incomplete" in body
    assert "Check/source: `ci`" in body
    assert "Required queued checks: `1`" in body
    assert "Missing required contexts: `1`" in body
    assert "Required context has not reported yet." in body


def test_action_report_green_comment_surfaces_evidence_review_signal() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    evidence_narrative = {
        "quality": {"ok": True, "coverage_percent": "96.69%"},
        "primary_signal": {
            "kind": "review_signal",
            "surface": "workflow",
            "title": "Required checks are not complete",
        },
        "graph": {
            "node_count": 1,
            "review_first_count": 1,
            "critical_count": 1,
            "top_blocker": {
                "title": "Required checks are not complete",
                "surface": "workflow",
                "action": "review",
                "review_first": True,
            },
        },
        "next_proof": [
            "gh pr checks --required",
            "python -m pre_commit run -a",
        ],
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        evidence_narrative=evidence_narrative,
    )

    assert "SDETKit Review Result: Green with evidence review" in body
    assert "Status: `green`" in body
    assert "## Evidence review signal" in body
    assert "Review signal: `present`" in body
    assert "Surface: `workflow`" in body
    assert "Required checks are not complete" in body
    assert "Operator action: `review`" in body
    assert "Gate interpretation: `quality gate passed; evidence review still required`" in body
    assert "Failure status: `not a failed quality gate and not a failed required check`" in body
    assert "Merge impact: `human review required before merge`" in body
    assert "Automation boundary: `no auto-remediation or security dismissal attempted`" in body
    assert "Review action: `review the listed workflow evidence before merge`" in body
    assert "`gh pr checks --required`" in body
    assert (
        "Evidence review signal present; quality gate passed, but review-first evidence requires human review before merge."
        in body
    )
    assert "No action required from SDETKit." not in body
    assert "Quality is green, so the review focus is not coverage." not in body
    assert "The comment must guide maintainers" not in body
    assert "Confirm the graph findings match the changed files and artifacts." not in body


def test_action_report_green_comment_distinguishes_proof_signal_from_review_signal() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    evidence_narrative = {
        "quality": {"ok": True, "coverage_percent": "96.69%"},
        "primary_signal": {
            "kind": "review_signal",
            "surface": "pr_quality",
            "title": "PR Quality evidence changed",
        },
        "graph": {
            "node_count": 2,
            "review_first_count": 0,
            "critical_count": 0,
            "top_blocker": {
                "title": "PR Quality evidence changed",
                "surface": "pr_quality",
                "action": "rerun_proof",
                "review_first": False,
            },
        },
        "next_proof": [
            "python -m pytest -q tests/test_pr_quality_evidence_narrative.py -o addopts=",
            "python -m pre_commit run -a",
        ],
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        evidence_narrative=evidence_narrative,
    )

    assert "SDETKit Review Result: Green with proof signal" in body
    assert "Status: `green`" in body
    assert "## Evidence proof signal" in body
    assert "Proof signal: `present`" in body
    assert "Surface: `pr_quality`" in body
    assert "PR Quality evidence changed" in body
    assert "Operator action: `rerun_proof`" in body
    assert "Review-first nodes: `0`" in body
    assert "Critical nodes: `0`" in body
    assert "Evidence proof signal present; verify the listed proof before routine merge." in body
    assert "## Evidence review signal" not in body
    assert "Review signal: `present`" not in body
    assert (
        "Evidence review signal present; quality gate passed, but review-first evidence requires human review before merge."
        not in body
    )
    assert "No action required from SDETKit." not in body


def test_write_comment_body_preserves_evidence_review_signal_artifact(
    tmp_path: Path,
) -> None:
    action_path = _write_json(
        tmp_path / "build/pr-quality/check-intelligence/action-report.json",
        {
            "status": "green",
            "primary_blocker": {},
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": "no remediation needed",
            },
            "recommended_actions": [],
            "proof_commands": [],
            "evidence": {},
        },
    )
    intelligence_path = _write_json(
        tmp_path / "build/pr-quality/check-intelligence/check-intelligence.json",
        {
            "checks_seen": 44,
            "failed_checks": [],
            "queued_checks": [],
            "startup_failures": [],
            "security_review": {"collected": True, "unresolved_findings": 0},
        },
    )
    narrative_path = _write_json(
        tmp_path / "build/pr-quality/pr-evidence-narrative.json",
        {
            "quality": {"ok": True, "coverage_percent": "96.69%"},
            "primary_signal": {
                "kind": "review_signal",
                "surface": "workflow",
                "title": "Required checks are not complete",
            },
            "graph": {
                "node_count": 1,
                "review_first_count": 1,
                "critical_count": 1,
                "top_blocker": {
                    "title": "Required checks are not complete",
                    "surface": "workflow",
                    "action": "review",
                    "review_first": True,
                },
            },
            "next_proof": ["gh pr checks --required"],
        },
    )
    out = tmp_path / "build/pr-quality/pr-comment-body.md"

    result = report.write_comment_body(
        action_report_path=action_path,
        check_intelligence_path=intelligence_path,
        evidence_narrative_path=narrative_path,
        out=out,
    )

    body = out.read_text(encoding="utf-8")
    assert result["out"] == out.as_posix()
    assert result["status"] == "green"
    assert result["result_title"] == "Green with evidence review"
    assert result["evidence_signal_kind"] == "review"
    assert result["evidence_signal_present"] is True
    assert result["evidence_review_required"] is True
    assert "SDETKit Review Result: Green with evidence review" in body
    assert "Status: `green`" in body
    assert "## Evidence review signal" in body
    assert "Review signal: `present`" in body
    assert "Surface: `workflow`" in body
    assert "Required checks are not complete" in body
    assert "Operator action: `review`" in body
    assert "Gate interpretation: `quality gate passed; evidence review still required`" in body
    assert "Failure status: `not a failed quality gate and not a failed required check`" in body
    assert "Merge impact: `human review required before merge`" in body
    assert "Automation boundary: `no auto-remediation or security dismissal attempted`" in body
    assert "Review action: `review the listed workflow evidence before merge`" in body
    assert "`gh pr checks --required`" in body
    assert (
        "Evidence review signal present; quality gate passed, but review-first evidence requires human review before merge."
        in body
    )
    assert "## Evidence proof signal" not in body
    assert "No action required from SDETKit." not in body


def test_write_comment_body_preserves_evidence_proof_signal_artifact(
    tmp_path: Path,
) -> None:
    action_path = _write_json(
        tmp_path / "build/pr-quality/check-intelligence/action-report.json",
        {
            "status": "green",
            "primary_blocker": {},
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": "no remediation needed",
            },
            "recommended_actions": [],
            "proof_commands": [],
            "evidence": {},
        },
    )
    intelligence_path = _write_json(
        tmp_path / "build/pr-quality/check-intelligence/check-intelligence.json",
        {
            "checks_seen": 44,
            "failed_checks": [],
            "queued_checks": [],
            "startup_failures": [],
            "security_review": {"collected": True, "unresolved_findings": 0},
        },
    )
    narrative_path = _write_json(
        tmp_path / "build/pr-quality/pr-evidence-narrative.json",
        {
            "quality": {"ok": True, "coverage_percent": "96.69%"},
            "primary_signal": {
                "kind": "review_signal",
                "surface": "pr_quality",
                "title": "PR Quality evidence changed",
            },
            "graph": {
                "node_count": 2,
                "review_first_count": 0,
                "critical_count": 0,
                "top_blocker": {
                    "title": "PR Quality evidence changed",
                    "surface": "pr_quality",
                    "action": "rerun_proof",
                    "review_first": False,
                },
            },
            "next_proof": [
                "python -m pytest -q tests/test_pr_quality_evidence_narrative.py -o addopts=",
                "python -m pre_commit run -a",
            ],
        },
    )
    out = tmp_path / "build/pr-quality/pr-comment-body.md"

    result = report.write_comment_body(
        action_report_path=action_path,
        check_intelligence_path=intelligence_path,
        evidence_narrative_path=narrative_path,
        out=out,
    )

    body = out.read_text(encoding="utf-8")
    assert result["out"] == out.as_posix()
    assert result["status"] == "green"
    assert result["result_title"] == "Green with proof signal"
    assert result["evidence_signal_kind"] == "proof"
    assert result["evidence_signal_present"] is True
    assert result["evidence_review_required"] is False
    assert "SDETKit Review Result: Green with proof signal" in body
    assert "Status: `green`" in body
    assert "## Evidence proof signal" in body
    assert "Proof signal: `present`" in body
    assert "Surface: `pr_quality`" in body
    assert "PR Quality evidence changed" in body
    assert "Operator action: `rerun_proof`" in body
    assert "Review-first nodes: `0`" in body
    assert "Critical nodes: `0`" in body
    assert "Evidence proof signal present; verify the listed proof before routine merge." in body
    assert "## Evidence review signal" not in body
    assert "Review signal: `present`" not in body
    assert (
        "Evidence review signal present; quality gate passed, but review-first evidence requires human review before merge."
        not in body
    )
    assert "No action required from SDETKit." not in body


def test_action_report_security_review_signal_explains_green_gate_review_route() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 1},
    }
    evidence_narrative = {
        "quality": {"ok": True, "coverage_percent": "96.69%"},
        "primary_signal": {
            "kind": "review_signal",
            "surface": "security",
            "title": "Security review requires action in tests/test_example.py",
        },
        "graph": {
            "node_count": 1,
            "review_first_count": 1,
            "critical_count": 0,
            "top_blocker": {
                "title": "Security review requires action in tests/test_example.py",
                "surface": "security",
                "action": "review",
                "review_first": True,
            },
        },
        "next_proof": [
            "Review unresolved GitHub Advanced Security comments on the PR.",
            "Fix the flagged surface or dismiss the false positive with a review reason.",
            "python -m sdetkit security check --root . --format json",
        ],
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        evidence_narrative=evidence_narrative,
    )

    assert "SDETKit Review Result: Green with evidence review" in body
    assert "Status: `green`" in body
    assert "Quality gate: `passed`" in body
    assert "Failed checks: `0`" in body
    assert "Unresolved security findings: `1`" in body
    assert "Surface: `security`" in body
    assert "Operator action: `review`" in body
    assert "Gate interpretation: `quality gate passed; evidence review still required`" in body
    assert "Failure status: `not a failed quality gate and not a failed required check`" in body
    assert "Merge impact: `human review required before merge`" in body
    assert "Automation boundary: `no auto-remediation or security dismissal attempted`" in body
    assert (
        "Security review action: `fix the PR-owned security finding or dismiss the false positive with a review reason`"
        in body
    )
    assert (
        "Evidence review signal present; quality gate passed, but review-first evidence requires human review before merge."
        in body
    )
    assert "No action required from SDETKit." not in body


def test_action_report_surfaces_review_first_patch_plan_handoff() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    evidence_narrative = {
        "quality": {"ok": True, "coverage_percent": "96.69%"},
        "primary_signal": {
            "kind": "proof_signal",
            "surface": "pr_quality",
            "title": "PR Quality evidence changed",
        },
        "graph": {
            "node_count": 2,
            "review_first_count": 0,
            "critical_count": 0,
            "top_blocker": {
                "title": "PR Quality evidence changed",
                "surface": "pr_quality",
                "action": "rerun_proof",
                "review_first": False,
            },
        },
        "patch_plan": {
            "enabled": True,
            "ok": True,
            "status": "review_required",
            "source_kind": "evidence_graph",
            "source_code": "security-review",
            "safe_to_auto_fix": False,
            "dry_run_only": True,
            "requires_human_review": True,
            "proof_commands": ["python -m sdetkit security check --root . --format json"],
            "recommended_commands": [
                "Review unresolved GitHub Advanced Security comments on the PR."
            ],
            "patch_step_count": 4,
        },
        "next_proof": [
            "python -m pytest -q tests/test_pr_quality_evidence_narrative.py -o addopts=",
            "python -m pre_commit run -a",
        ],
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        evidence_narrative=evidence_narrative,
    )

    assert "SDETKit Review Result: Green with proof signal" in body
    assert "<summary><strong>Review-first patch plan</strong></summary>" in body
    assert "Status: `review_required`" in body
    assert "Source kind: `evidence_graph`" in body
    assert "Source code: `security-review`" in body
    assert "Safe to auto-fix: `false`" in body
    assert "Dry run only: `true`" in body
    assert "Requires human review: `true`" in body
    assert "Patch steps: `4`" in body
    assert "python -m sdetkit security check --root . --format json" in body
    assert "Review unresolved GitHub Advanced Security comments on the PR." in body


def test_action_report_reconciles_cleared_security_review_signal() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 43,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "missing_required_contexts": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    evidence_narrative = {
        "quality": {"ok": True, "coverage_percent": "96.69%"},
        "primary_signal": {
            "kind": "review_signal",
            "surface": "security",
            "title": "Security review requires action in tests/test_example.py",
        },
        "graph": {
            "node_count": 3,
            "review_first_count": 1,
            "critical_count": 0,
            "top_blocker": {
                "title": "Security review requires action in tests/test_example.py",
                "surface": "security",
                "action": "review",
                "review_first": True,
            },
        },
        "next_proof": [
            "Review unresolved GitHub Advanced Security comments on the PR.",
            "Fix the flagged surface or dismiss the false positive with a review reason.",
        ],
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        evidence_narrative=evidence_narrative,
    )

    assert "SDETKit Review Result: Green with proof signal" in body
    assert "## Evidence proof signal" in body
    assert "Security review cleared for changed code" in body
    assert "latest security review has no unresolved PR-owned findings" in body
    assert "Unresolved security findings: `0`" in body
    assert "no fix or dismissal required for PR-owned security findings" in body
    assert "SDETKit Review Result: Green with evidence review" not in body
    assert "Evidence review signal present; quality gate passed" not in body
    assert "human review required before merge" not in body
    assert "Fix the flagged surface or dismiss the false positive" not in body
    assert "### Proof to rerun" in body
    assert "`none`" in body


def test_action_report_comment_renders_failed_check_first_failure() -> None:
    action = {
        "status": "review_required",
        "primary_blocker": {
            "check": "Fast CI lane (py3.12)",
            "title": "Type contract drift detected",
            "surface": "quality",
            "code": "MYPY_TYPE_CONTRACT_DRIFT",
            "url": "https://github.example/check",
            "impact": "Inspect the first failing line before broad rewrites.",
            "first_failure": {
                "line_number": 12,
                "line": "src/sdetkit/example.py:10: error: Incompatible return value type",
                "tool": "mypy",
                "kind": "type_contract",
            },
            "first_failure_line": "src/sdetkit/example.py:10: error: Incompatible return value type",
            check_intelligence.FAILED_STEP_EVIDENCE_KEY: {
                "status": "found",
                "command": "python -m mypy src",
                "source": "github_actions_group",
                "line_number": 4,
                "failure_line_number": 12,
                "reporting_only": True,
                "automation_allowed": False,
                "merge_authorized": False,
            },
        },
        "automation": {"attempted": False, "allowed": False, "reason": "review-first"},
        "recommended_actions": ["Fix the first reported contract violation."],
        "proof_commands": ["python -m mypy src"],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 1,
        "failed_checks": [
            {
                "name": "Fast CI lane (py3.12)",
                "safe_to_auto_fix": False,
                "diagnosis": {
                    "code": "MYPY_TYPE_CONTRACT_DRIFT",
                    "title": "Type contract drift detected",
                },
                "first_failure": {
                    "line_number": 12,
                    "line": "src/sdetkit/example.py:10: error: Incompatible return value type",
                    "tool": "mypy",
                    "kind": "type_contract",
                },
                check_intelligence.FAILED_STEP_EVIDENCE_KEY: {
                    "status": "found",
                    "command": "python -m mypy src",
                    "source": "github_actions_group",
                    "line_number": 4,
                    "failure_line_number": 12,
                    "reporting_only": True,
                    "automation_allowed": False,
                    "merge_authorized": False,
                },
            }
        ],
        "queued_checks": [],
        "startup_failures": [],
        "missing_required_contexts": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }

    body = report.render_comment_body(action_report=action, check_intelligence=intelligence)

    assert (
        "First failure: `src/sdetkit/example.py:10: error: Incompatible return value type`" in body
    )
    assert "Failure location: `line 12`" in body
    assert "Failure tool/kind: `mypy` / `type_contract`" in body
    assert "Failed step evidence: `found`" in body
    assert "Failed command: `python -m mypy src`" in body
    assert "Failed step reporting only: `true`" in body
    assert "Failed step automation allowed: `false`" in body


def test_action_report_comment_renders_safe_remediation_eligibility() -> None:
    action = {
        "status": "review_required",
        "primary_blocker": {
            "check": "autopilot",
            "title": "Formatter drift blocked pre-commit",
            "surface": "quality",
            "code": "PRE_COMMIT_FORMAT_DRIFT",
            "first_failure": {
                "line_number": 3,
                "line": "- files were modified by this hook",
                "tool": "pre_commit",
                "kind": "format_drift",
            },
            "first_failure_line": "- files were modified by this hook",
            "safe_to_auto_fix": True,
            "safe_remediation": {
                "safe_to_auto_fix": True,
                "strategy": "run_pre_commit",
                "reason": "Failure is limited to deterministic formatting or whitespace hooks.",
            },
        },
        "automation": {"attempted": False, "allowed": True, "reason": "safe formatting only"},
        "recommended_actions": ["Run pre-commit and commit formatting changes."],
        "proof_commands": ["python -m pre_commit run -a"],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 1,
        "failed_checks": [
            {
                "name": "autopilot",
                "safe_to_auto_fix": True,
                "diagnosis": {
                    "code": "PRE_COMMIT_FORMAT_DRIFT",
                    "title": "Formatter drift blocked pre-commit",
                },
                "first_failure": {
                    "line_number": 3,
                    "line": "- files were modified by this hook",
                    "tool": "pre_commit",
                    "kind": "format_drift",
                },
                "safe_remediation": {
                    "safe_to_auto_fix": True,
                    "strategy": "run_pre_commit",
                    "reason": "Failure is limited to deterministic formatting or whitespace hooks.",
                },
            }
        ],
        "queued_checks": [],
        "startup_failures": [],
        "missing_required_contexts": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }

    body = report.render_comment_body(action_report=action, check_intelligence=intelligence)

    assert "Safe remediation: `run_pre_commit`" in body
    assert (
        "Safe reason: `Failure is limited to deterministic formatting or whitespace hooks.`" in body
    )


def test_action_report_comment_renders_safe_fix_outcome() -> None:
    action = {
        "status": "green",
        "quality_gate": {"passed": True, "coverage": 96.69},
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
    }
    intelligence = {
        "summary": {
            "failed_check_count": 0,
            "queued_check_count": 0,
            "required_queued_check_count": 0,
            "missing_required_context_count": 0,
            "startup_failure_count": 0,
            "required_startup_failure_count": 0,
            "security_review": {"collected": True, "unresolved_findings": 0},
        },
        "failed_checks": [],
        "safe_fix_outcome": {
            "status": "pushed",
            "attempted": True,
            "remediation_ok": True,
            "committed": True,
            "pushed": True,
            "commit_sha": "abc123",
            "affected_files": ["tests/test_example.py"],
            "reason": "PR Quality safe-remediation bridge executed",
            "proof_commands": ["python -m pre_commit run -a"],
        },
    }

    body = report.render_comment_body(action_report=action, check_intelligence=intelligence)

    assert "<summary><strong>Safe fix outcome</strong></summary>" in body
    assert "- Status: `pushed`" in body
    assert "- Attempted: `true`" in body
    assert "- Committed: `true`" in body
    assert "- Pushed: `true`" in body
    assert "- Commit SHA: `abc123`" in body
    assert "`tests/test_example.py`" in body
    assert "- Proof after fix:" in body
    assert "`python -m pre_commit run -a`" in body


def test_action_report_comment_renders_freshness_formatter_and_gate_fallout_details() -> None:
    from sdetkit.pr_quality_action_report import render_comment_body

    action_report = {
        "status": "review_required",
        "primary_blocker": {
            "check": "autopilot",
            "title": "Formatter drift blocked pre-commit",
            "surface": "quality",
            "code": "PRE_COMMIT_FORMAT_DRIFT",
            "first_failure": {"line": "- files were modified by this hook", "line_number": 30},
            "first_failure_line": "- files were modified by this hook",
            "formatter_changed_files": ["src/sdetkit/example.py"],
            "stale_evidence": False,
            "outside_changed_files": ["templates/platform_problem/rich/problem.py"],
            "possible_changed_files_gate_fallout": True,
            "safe_to_auto_fix": True,
            "safe_remediation": {
                "safe_to_auto_fix": True,
                "strategy": "run_pre_commit",
                "reason": "Failure is limited to deterministic formatting or whitespace hooks.",
            },
        },
        "automation": {"attempted": False, "allowed": True, "reason": "safe formatting"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    check_intelligence = {
        "failed_checks": [
            {
                "name": "autopilot",
                "diagnosis": {
                    "code": "PRE_COMMIT_FORMAT_DRIFT",
                    "title": "Formatter drift blocked pre-commit",
                },
                "first_failure": {"line": "- files were modified by this hook", "line_number": 30},
                "safe_to_auto_fix": True,
                "formatter_changed_files": ["src/sdetkit/example.py"],
                "outside_changed_files": ["templates/platform_problem/rich/problem.py"],
                "possible_changed_files_gate_fallout": True,
                "safe_remediation": {
                    "safe_to_auto_fix": True,
                    "strategy": "run_pre_commit",
                    "reason": "Failure is limited to deterministic formatting or whitespace hooks.",
                },
            }
        ],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {},
    }

    body = render_comment_body(
        action_report=action_report,
        check_intelligence=check_intelligence,
    )

    assert "Formatter changed files: `src/sdetkit/example.py`" in body
    assert "Outside PR changed set: `templates/platform_problem/rich/problem.py`" in body
    assert "Gate fallout: possible changed-files base-resolution issue" in body


def test_action_report_comment_renders_remediation_refresh_loop_summary() -> None:
    from sdetkit.pr_quality_action_report import render_comment_body

    action_report = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    check_intelligence = {
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {},
        "remediation_refresh": {
            "safe_fix_attempted": True,
            "safe_fix_committed": True,
            "safe_fix_pushed": True,
            "safe_fix_commit_sha": "new123",
            "previous_head_sha": "old111",
            "refreshed_head_sha": "new123",
            "proof_after_fix_started": True,
            "proof_after_fix_passed": True,
            "proof_after_fix_failed": False,
            "remaining_failed_checks": [],
            "remaining_review_first_blockers": [],
            "merge_assessment": "green_after_safe_fix",
        },
    }

    body = render_comment_body(
        action_report=action_report,
        check_intelligence=check_intelligence,
    )

    assert "Remediation refresh" in body
    assert "Safe fix pushed to branch." in body
    assert "Refreshed head SHA: `new123`" in body
    assert "Proof after fix result: `passed`" in body
    assert "Remaining blockers: none" in body
    assert "Merge assessment: `green_after_safe_fix`" in body


def test_pr_quality_action_report_renders_dependency_audit_evidence() -> None:
    from sdetkit import pr_quality_action_report as report

    body = report.render_comment_body(
        action_report={
            "status": "review_required",
            "quality_gate": "passed",
            "coverage": 96.69,
            "operator_action": "review",
            "review_first": True,
            "primary_blocker": {
                "check_name": "audit",
                "title": "Dependency audit reported vulnerable packages",
                "surface": "dependency",
                "code": "DEPENDENCY_AUDIT_VULNERABILITY",
                "safe_to_auto_fix": False,
                "review_first": True,
                "first_failure": {
                    "line": "Found 1 known vulnerability in 1 package",
                    "line_number": 300,
                    "tool": "pip-audit",
                    "kind": "dependency_vulnerability",
                },
                "dependency_audit": {
                    "vulnerability_count": 1,
                    "package_count": 1,
                    "command": "pip-audit --format json -o pip-audit-report.json -r requirements-test.txt -r requirements-docs.txt --ignore-vuln CVE-2026-4539",
                    "report_path": "pip-audit-report.json",
                    "artifact_url": "https://github.com/example/actions/runs/1/artifacts/2",
                    "ignored_vulnerabilities": ["CVE-2026-4539"],
                },
                "owner_files": [
                    "requirements-test.txt",
                    "requirements-docs.txt",
                    "constraints-ci.txt",
                    "pyproject.toml",
                    ".github/workflows/",
                ],
            },
            "recommended_actions": [
                "Review pip-audit-report.json for package/advisory/fixed-version details.",
                "Create a dependency-only PR if the finding is not baseline-approved.",
            ],
            "required_proof": [
                "python -m pip install -c constraints-ci.txt -r requirements-test.txt -r requirements-docs.txt -e .",
            ],
        },
        check_intelligence={
            "failed_checks": [
                {
                    "name": "audit",
                    "surface": "dependency",
                    "code": "DEPENDENCY_AUDIT_VULNERABILITY",
                    "title": "Dependency audit reported vulnerable packages",
                    "safe_to_auto_fix": False,
                    "dependency_audit": {
                        "vulnerability_count": 1,
                        "package_count": 1,
                        "report_path": "pip-audit-report.json",
                        "artifact_url": "https://github.com/example/actions/runs/1/artifacts/2",
                    },
                }
            ],
            "checks_seen": 44,
            "failed_checks_count": 1,
            "queued_checks_count": 0,
            "required_queued_checks_count": 0,
            "missing_required_contexts_count": 0,
            "startup_failures_count": 0,
            "required_startup_failures_count": 0,
            "security_review_collected": True,
            "unresolved_security_findings": 0,
        },
        safe_fix_outcome={},
    )

    assert "Dependency audit reported vulnerable packages" in body
    assert "DEPENDENCY_AUDIT_VULNERABILITY" in body
    assert "Found 1 known vulnerability in 1 package" in body
    assert "pip-audit-report.json" in body
    assert "https://github.com/example/actions/runs/1/artifacts/2" in body
    assert "requirements-test.txt" in body
    assert "constraints-ci.txt" in body
    assert "review_first" in body or "Review first" in body


def test_action_report_comment_shows_code_scanning_freshness_counts() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
        "code_scanning_review": {
            "collected": True,
            "open_alerts": 3,
            "current_alerts": 1,
            "stale_alerts": 2,
            "unknown_freshness_alerts": 0,
        },
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        evidence_narrative={"quality": {"ok": True, "coverage_percent": "96.69%"}},
    )

    assert "Code scanning review collected: `true`" in body
    assert "Open code scanning alerts: `3`" in body
    assert "Current code scanning alerts: `1`" in body
    assert "Stale code scanning alerts: `2`" in body


def _trajectory_records() -> list[dict]:
    return [
        {
            "schema_version": "sdetkit.trajectory.v1",
            "diagnostic_id": "formatting-autopilot",
            "action": "run_pre_commit",
            "diagnosis": {
                "failure_class": "formatter_only",
                "risk_surface": "formatting",
            },
            "decision": {
                "review_first": False,
                "auto_fix_allowed": True,
                "reason": "safe mechanical remediation candidate",
            },
            "final_result": "safe_fix_candidate",
        },
        {
            "schema_version": "sdetkit.trajectory.v1",
            "diagnostic_id": "release-review",
            "action": "rebuild_release_artifacts",
            "diagnosis": {
                "failure_class": "release_artifact_invalid",
                "risk_surface": "release",
            },
            "decision": {
                "review_first": True,
                "auto_fix_allowed": False,
                "reason": "release failures require human review",
            },
            "final_result": "review_required",
        },
    ]


def test_action_report_comment_surfaces_trajectory_summary() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 12,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        trajectory_records=_trajectory_records(),
    )

    assert "<summary><strong>Trajectory summary</strong></summary>" in body
    assert "Records: `2`" in body
    assert "Review-first decisions: `1`" in body
    assert "Auto-fix allowed decisions: `1`" in body
    assert "`review_required`=1" in body
    assert "`safe_fix_candidate`=1" in body
    assert "`formatting-autopilot`: action=`run_pre_commit`" in body
    assert "auto_fix_allowed=`true`" in body
    assert "`release-review`: action=`rebuild_release_artifacts`" in body
    assert "review_first=`true`" in body


def test_write_comment_body_reads_trajectory_jsonl_and_reports_metadata(
    tmp_path: Path,
) -> None:
    action_path = _write_json(
        tmp_path / "action-report.json",
        {
            "status": "green",
            "primary_blocker": {},
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": "no remediation needed",
            },
            "recommended_actions": [],
            "proof_commands": [],
            "evidence": {},
        },
    )
    intelligence_path = _write_json(
        tmp_path / "check-intelligence.json",
        {
            "checks_seen": 12,
            "failed_checks": [],
            "queued_checks": [],
            "startup_failures": [],
            "security_review": {"collected": True, "unresolved_findings": 0},
        },
    )
    trajectory_path = tmp_path / "trajectory.jsonl"
    trajectory_path.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in _trajectory_records()) + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "comment.md"

    result = report.write_comment_body(
        action_report_path=action_path,
        check_intelligence_path=intelligence_path,
        trajectory_jsonl_path=trajectory_path,
        out=out,
    )

    body = out.read_text(encoding="utf-8")
    assert result["trajectory_signal_present"] is True
    assert result["trajectory_record_count"] == 2
    assert result["trajectory_review_first_count"] == 1
    assert result["trajectory_auto_fix_allowed_count"] == 1
    assert "<summary><strong>Trajectory summary</strong></summary>" in body
    assert "Records: `2`" in body


def test_action_report_cli_accepts_trajectory_jsonl(tmp_path: Path, capsys) -> None:
    action_path = _write_json(
        tmp_path / "action-report.json",
        {
            "status": "green",
            "primary_blocker": {},
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": "no remediation needed",
            },
            "recommended_actions": [],
            "proof_commands": [],
            "evidence": {},
        },
    )
    intelligence_path = _write_json(
        tmp_path / "check-intelligence.json",
        {
            "checks_seen": 12,
            "failed_checks": [],
            "queued_checks": [],
            "startup_failures": [],
            "security_review": {"collected": True, "unresolved_findings": 0},
        },
    )
    trajectory_path = tmp_path / "trajectory.jsonl"
    trajectory_path.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in _trajectory_records()) + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "comment.md"

    rc = report.main(
        [
            "--action-report",
            str(action_path),
            "--check-intelligence",
            str(intelligence_path),
            "--trajectory-jsonl",
            str(trajectory_path),
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["trajectory_signal_present"] is True
    assert printed["trajectory_record_count"] == 2
    assert printed["trajectory_review_first_count"] == 1
    assert printed["trajectory_auto_fix_allowed_count"] == 1
    assert "<summary><strong>Trajectory summary</strong></summary>" in out.read_text(
        encoding="utf-8"
    )


def test_comment_does_not_clear_unresolved_security_review_evidence() -> None:
    from sdetkit import pr_quality_action_report as report

    body = report.render_comment_body(
        action_report={
            "status": "review_required",
            "primary_blocker": {
                "check": "GitHub security review",
                "title": "Security review requires action in src/sdetkit/protected_verifier.py",
                "surface": "security",
                "code": "_".join(("SECURITY", "REVIEW", "FINDING")),
                "path": "src/sdetkit/protected_verifier.py",
                "line": 141,
                "impact": "An unresolved security review finding requires human review.",
            },
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": (
                    "security review findings are review-first and cannot be auto-dismissed"
                ),
            },
            "recommended_actions": [],
            "proof_commands": [],
        },
        check_intelligence={
            "checks_seen": 1,
            "failed_checks": [],
            "queued_checks": [],
            "startup_failures": [],
            "missing_required_contexts": [],
            "security_review": {
                "collected": True,
                "unresolved_findings": 1,
                "findings": [],
            },
            "code_scanning_review": {},
        },
        evidence_narrative={
            "quality": {"ok": True, "coverage_percent": "96.69"},
            "primary_signal": {
                "kind": "review_signal",
                "surface": "security",
                "title": "Security review requires action",
            },
            "graph": {
                "node_count": 1,
                "review_first_count": 1,
                "critical_count": 1,
                "top_blocker": {
                    "title": "Security review requires action",
                    "surface": "security",
                    "action": "review",
                    "review_first": True,
                },
            },
        },
    )

    assert "SDETKit Review Result: Action required" in body
    assert "Unresolved security findings: `1`" in body
    assert "- File: `src/sdetkit/protected_verifier.py:141`" in body
    assert "Security review cleared for changed code" not in body


def test_action_report_renders_current_code_scanning_alert_location() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 1,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
        "code_scanning_review": {
            "collected": True,
            "collection_status": "collected",
            "collection_reason": "",
            "open_alerts": 2,
            "current_alerts": 1,
            "stale_alerts": 1,
            "unknown_freshness_alerts": 0,
            "findings": [
                {
                    "freshness": "current",
                    "path": "src/sdetkit/current.py",
                    "line": "14",
                    "rule_id": "py/example",
                    "severity": "warning",
                    "recommended_action": "fix_current_alert_or_dismiss_reviewed_false_positive",
                },
                {
                    "freshness": "stale",
                    "path": "src/sdetkit/old.py",
                    "line": "20",
                    "rule_id": "py/example",
                    "severity": "warning",
                    "recommended_action": "wait_for_code_scanning_refresh",
                },
            ],
        },
    }

    body = report.render_comment_body(action_report=action, check_intelligence=intelligence)

    assert "Code scanning review collected: `true`" in body
    assert "Code scanning collection status: `collected`" in body
    assert "Current code scanning alerts: `1`" in body
    assert "Stale code scanning alerts: `1`" in body
    assert "Code scanning current finding: `src/sdetkit/current.py:14`" in body
    assert "action=`fix_current_alert_or_dismiss_reviewed_false_positive`" in body
    assert "Code scanning stale finding: `src/sdetkit/old.py:20`" in body


def test_action_report_renders_unavailable_code_scanning_collection() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 1,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
        "code_scanning_review": {
            "collected": False,
            "collection_status": "unavailable",
            "collection_reason": "GitHub code-scanning alerts API was unavailable or not permitted.",
            "open_alerts": 0,
            "current_alerts": 0,
            "stale_alerts": 0,
            "unknown_freshness_alerts": 0,
            "findings": [],
        },
    }

    body = report.render_comment_body(action_report=action, check_intelligence=intelligence)

    assert "Code scanning review collected: `false`" in body
    assert "Code scanning collection status: `unavailable`" in body
    assert "GitHub code-scanning alerts API was unavailable or not permitted." in body


def test_action_report_promotes_current_code_scanning_alert_to_security_blocker() -> None:
    intelligence = {
        "checks_seen": 1,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
        "code_scanning_review": {
            "collected": True,
            "collection_status": "collected",
            "collection_reason": "",
            "open_alerts": 1,
            "current_alerts": 1,
            "stale_alerts": 0,
            "unknown_freshness_alerts": 0,
            "findings": [
                {
                    "freshness": "current",
                    "url": "https://example.test/code-scanning/44",
                    "path": "src/sdetkit/current.py",
                    "line": "14",
                    "rule_id": "py/example",
                    "severity": "warning",
                    "message": "Current code-scanning alert on changed code.",
                    "recommended_action": "fix_current_alert_or_dismiss_reviewed_false_positive",
                }
            ],
        },
    }

    action = check_intelligence.build_action_report(intelligence)
    body = report.render_comment_body(action_report=action, check_intelligence=intelligence)

    assert action["status"] == "review_required"
    assert action["primary_blocker"]["surface"] == "security"
    assert action["primary_blocker"]["code"] == check_intelligence.CODE_SCANNING_CURRENT_ALERT
    assert action["automation"]["allowed"] is False
    assert "SDETKit Review Result: Action required" in body
    assert "Current code scanning alert requires action" in body
    assert "src/sdetkit/current.py:14" in body
    assert "Current code scanning alerts: `1`" in body
    assert "Code scanning current finding: `src/sdetkit/current.py:14`" in body


def test_action_report_renders_runtime_proof_artifacts_without_authority() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    runtime = {
        "status": "collected",
        "isolated_proof": {
            "status": "passed",
            "git_inventory_verified": True,
            "runtime_guard_checked": True,
            "runtime_guard_passed": True,
            "runtime_guard_violation_count": 0,
            "network_boundary_status": "not_requested",
            "network_isolation_enforced": False,
            "profiles_executed": 1,
            "profiles_blocked": 0,
        },
        "live_benchmark": {"collection_status": "not_collected"},
        "repo_memory": {"collection_status": "not_collected"},
        "trusted_diagnostic_signal_snapshot_history": {
            "collection_status": "collected",
            "status": "trusted_diagnostic_signal_snapshot_history_verified",
            "source_workflow": "repo-memory-history.yml",
            "latest_accepted_main_head": "abc123",
            "base_ancestry_verified": True,
            "record_count": 3,
            "quiet_green_advisory_baseline_record_count": 1,
            "review_signal_record_count": 2,
            "integration_proof_signal_record_count": 1,
            "latest_snapshot_status": "diagnostic_signal_observed",
            "latest_primary_signal_kind": "review_signal",
            "advisor_false_positive_rate_status": "requires_reviewed_history",
            "prior_history_is_read_only_input": True,
            "reporting_only": True,
            "current_pr_decision_input": False,
            "feeds_repo_memory": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
            "historical_snapshot_authorizes_current_action": False,
        },
        "decision_boundary": {
            "proof_commands_executed_by_renderer": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        runtime_proof_artifacts=runtime,
    )

    assert "<summary><strong>Runtime proof artifacts</strong></summary>" in body
    assert "Isolated proof status: `passed`" in body
    assert "Git inventory verified: `true`" in body
    assert "Runtime guard passed: `true`" in body
    assert "Runtime guard violations: `0`" in body
    assert "Network isolation enforced: `false`" in body
    assert "Live benchmark collection status: `not_collected`" in body
    assert "RepoMemory collection status: `not_collected`" in body
    assert "Proof commands executed by renderer: `false`" in body
    assert "Automation allowed by runtime artifacts: `false`" in body
    assert "Merge authorized by runtime artifacts: `false`" in body
    assert "Trusted diagnostic signal snapshot history collection status: `collected`" in body
    assert "Trusted diagnostic signal snapshot history records: `3`" in body
    assert (
        "Trusted diagnostic signal snapshot history advisor false-positive rate status: "
        "`requires_reviewed_history`"
    ) in body
    assert "Historical snapshot authorizes current action: `false`" in body
    assert "Automation allowed by trusted diagnostic signal snapshot history: `false`" in body


def test_action_report_cli_reports_runtime_proof_metadata(tmp_path: Path, capsys) -> None:
    action_path = _write_json(
        tmp_path / "action-report.json",
        {
            "status": "green",
            "primary_blocker": {},
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": "no remediation needed",
            },
            "recommended_actions": [],
            "proof_commands": [],
        },
    )
    intelligence_path = _write_json(
        tmp_path / "check-intelligence.json",
        {
            "checks_seen": 1,
            "failed_checks": [],
            "queued_checks": [],
            "startup_failures": [],
        },
    )
    runtime_path = _write_json(
        tmp_path / "runtime-proof-artifacts.json",
        {
            "status": "collected",
            "isolated_proof": {
                "status": "passed",
                "runtime_guard_violation_count": 0,
            },
            "decision_boundary": {
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
    )
    out = tmp_path / "comment.md"

    rc = report.main(
        [
            "--action-report",
            str(action_path),
            "--check-intelligence",
            str(intelligence_path),
            "--runtime-proof-artifacts",
            str(runtime_path),
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["runtime_proof_artifacts_present"] is True
    assert printed["runtime_proof_collection_status"] == "collected"
    assert printed["runtime_guard_violation_count"] == 0
    assert "trusted_diagnostic_signal_snapshot_history_collection_status" not in printed
    assert "trusted_diagnostic_signal_snapshot_history_record_count" not in printed
    assert (
        "trusted_diagnostic_signal_snapshot_history_advisor_false_positive_rate_status"
        not in printed
    )
    assert (
        "trusted_diagnostic_signal_snapshot_history_historical_snapshot_authorizes_current_action"
        not in printed
    )
    assert "<summary><strong>Runtime proof artifacts</strong></summary>" in out.read_text(
        encoding="utf-8"
    )


def test_action_report_cli_keeps_trusted_diagnostic_history_out_of_stdout_metadata(
    tmp_path: Path,
    capsys,
) -> None:
    action_path = _write_json(
        tmp_path / "action-report.json",
        {
            "status": "green",
            "primary_blocker": {},
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": "no remediation needed",
            },
            "recommended_actions": [],
            "proof_commands": [],
        },
    )
    intelligence_path = _write_json(
        tmp_path / "check-intelligence.json",
        {
            "checks_seen": 1,
            "failed_checks": [],
            "queued_checks": [],
            "startup_failures": [],
        },
    )
    runtime_path = _write_json(
        tmp_path / "runtime-proof-artifacts.json",
        {
            "status": "collected",
            "isolated_proof": {
                "status": "passed",
                "runtime_guard_violation_count": 0,
            },
            "trusted_diagnostic_signal_snapshot_history": {
                "collection_status": "collected",
                "status": "trusted_diagnostic_signal_snapshot_history_verified",
                "source_workflow": "internal-history-source",
                "latest_accepted_main_head": "abc123",
                "base_ancestry_verified": True,
                "record_count": 4,
                "quiet_green_advisory_baseline_record_count": 2,
                "review_signal_record_count": 1,
                "integration_proof_signal_record_count": 1,
                "latest_snapshot_status": "diagnostic_signal_observed",
                "latest_primary_signal_kind": "review_signal",
                "advisor_false_positive_rate_status": "requires_reviewed_history",
                "prior_history_is_read_only_input": True,
                "reporting_only": True,
                "current_pr_decision_input": False,
                "feeds_repo_memory": False,
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
                "historical_snapshot_authorizes_current_action": False,
            },
            "decision_boundary": {
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
    )
    out = tmp_path / "comment.md"

    rc = report.main(
        [
            "--action-report",
            str(action_path),
            "--check-intelligence",
            str(intelligence_path),
            "--runtime-proof-artifacts",
            str(runtime_path),
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    stdout_text = capsys.readouterr().out
    printed = json.loads(stdout_text)

    assert printed["runtime_proof_artifacts_present"] is True
    assert printed["runtime_proof_collection_status"] == "collected"
    assert "trusted_diagnostic_signal_snapshot_history" not in stdout_text
    assert "internal-history-source" not in stdout_text
    assert "requires_reviewed_history" not in stdout_text

    body = out.read_text(encoding="utf-8")
    assert "Trusted diagnostic signal snapshot history collection status: `collected`" in body
    assert "Trusted diagnostic signal snapshot history records: `4`" in body
    assert (
        "Trusted diagnostic signal snapshot history advisor false-positive rate status: "
        "`requires_reviewed_history`"
    ) in body
    assert "Historical snapshot authorizes current action: `false`" in body


def test_action_report_renders_collected_live_benchmark_and_repo_memory() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {
            "attempted": False,
            "allowed": False,
            "reason": "no remediation needed",
        },
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 1,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
    }
    runtime = {
        "status": "collected",
        "isolated_proof": {
            "status": "passed",
            "git_inventory_verified": True,
            "runtime_guard_checked": True,
            "runtime_guard_passed": True,
            "runtime_guard_violation_count": 0,
            "network_boundary_status": "not_requested",
            "network_isolation_enforced": False,
            "profiles_executed": 1,
            "profiles_blocked": 0,
        },
        "live_benchmark": {
            "collection_status": "collected",
            "status": "passed",
            "scenario_count": 6,
            "passed_count": 6,
            "git_inventory_verified_count": 5,
            "expected_failed_evidence_count": 5,
            "network_boundary_blocked_count": 1,
            "anti_cheat_rejection_count": 2,
            "network_isolation_enforced_count": 0,
            "boundary_preserved": True,
        },
        "repo_memory": {
            "collection_status": "collected",
            "status": "live_proof_supported_memory",
            "live_contract_proven": True,
            "known_safe_candidate_count": 0,
            "live_safe_candidate_count": 0,
            "anti_cheat_rejection_scenario_count": 2,
        },
        "decision_boundary": {
            "proof_commands_executed_by_renderer": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        runtime_proof_artifacts=runtime,
    )

    assert "Live benchmark collection status: `collected`" in body
    assert "Live benchmark status: `passed`" in body
    assert "Live benchmark scenarios: `6`" in body
    assert "Live anti-cheat rejection scenarios: `2`" in body
    assert "Live benchmark boundary preserved: `true`" in body
    assert "RepoMemory collection status: `collected`" in body
    assert "RepoMemory status: `live_proof_supported_memory`" in body
    assert "RepoMemory live contract proven: `true`" in body
    assert "Automation allowed by runtime artifacts: `false`" in body


def test_action_report_renders_trusted_main_history_as_advisory_only() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {
            "attempted": False,
            "allowed": False,
            "reason": "no remediation needed",
        },
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    runtime = {
        "status": "collected",
        report.TRUSTED_HISTORY: {
            "collection_status": "collected",
            "status": "trusted_history_verified",
            "source_workflow": "RepoMemory Profile History",
            "latest_accepted_main_head": "accepted-main-head",
            report.BASE_ANCESTRY_VERIFIED: True,
            "record_count": 1,
            report.LIVE_PROVEN_RECORD_COUNT: 1,
            report.PRIOR_HISTORY_READ_ONLY_INPUT: True,
            report.PROOF_COMMANDS_EXECUTED_BY_READER: False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
        "decision_boundary": {
            "proof_commands_executed_by_renderer": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        runtime_proof_artifacts=runtime,
    )

    assert "Trusted history collection status: `collected`" in body
    assert "Trusted history status: `trusted_history_verified`" in body
    assert "Trusted history source workflow: `RepoMemory Profile History`" in body
    assert "Trusted history base ancestry verified: `true`" in body
    assert "Trusted history records: `1`" in body
    assert "Trusted history live-contract-proven records: `1`" in body
    assert "Trusted history prior input read-only: `true`" in body
    assert "Automation allowed by trusted history: `false`" in body
    assert "Merge authorized by trusted history: `false`" in body
    assert "Semantic equivalence proven by trusted history: `false`" in body


def test_write_comment_body_exports_trusted_history_visibility_metadata(
    tmp_path: Path,
) -> None:
    action_path = _write_json(
        tmp_path / "action-report.json",
        {
            "status": "green",
            "primary_blocker": {},
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": "no remediation needed",
            },
            "recommended_actions": [],
            "proof_commands": [],
            "evidence": {},
        },
    )
    intelligence_path = _write_json(
        tmp_path / "check-intelligence.json",
        {
            "checks_seen": 44,
            "failed_checks": [],
            "queued_checks": [],
            "startup_failures": [],
            "security_review": {"collected": True, "unresolved_findings": 0},
        },
    )
    runtime_path = _write_json(
        tmp_path / "runtime-proof-artifacts.json",
        {
            "status": "collected",
            report.TRUSTED_HISTORY: {
                "collection_status": "collected",
                "status": "trusted_history_verified",
                "record_count": 1,
                report.BASE_ANCESTRY_VERIFIED: True,
                report.PRIOR_HISTORY_READ_ONLY_INPUT: True,
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
    )

    result = report.write_comment_body(
        action_report_path=action_path,
        check_intelligence_path=intelligence_path,
        runtime_proof_artifacts_path=runtime_path,
        out=tmp_path / "comment.md",
    )

    assert result[report.TRUSTED_HISTORY_COLLECTION_STATUS] == "collected"
    assert result[report.TRUSTED_HISTORY_STATUS] == "trusted_history_verified"
    assert result[report.TRUSTED_HISTORY_RECORD_COUNT] == 1
    assert result[report.TRUSTED_HISTORY_BASE_ANCESTRY_VERIFIED] is True
    assert result[report.TRUSTED_HISTORY_PRIOR_INPUT_READ_ONLY] is True
    assert result[report.TRUSTED_HISTORY_AUTOMATION_ALLOWED] is False
    assert result[report.TRUSTED_HISTORY_MERGE_AUTHORIZED] is False
    assert result[report.TRUSTED_HISTORY_SEMANTIC_EQUIVALENCE_PROVEN] is False


def test_action_report_renders_sanitized_security_diagnosis_without_authority() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    security_diagnosis = {
        "collection_status": "collected",
        "summary": {
            "open_findings": 1,
            "current_findings": 1,
            "stale_findings": 0,
            "scanner_metadata_false_positive_candidates": 0,
            "intentional_test_fixture_candidates": 0,
            "safe_mechanical_fix_candidates": 1,
            "true_positive_fix_required": 0,
        },
        "decision_boundary": {
            report.AUTOMATIC_SECURITY_FIX_ALLOWED: False,
            report.AUTOMATIC_DISMISSAL_ALLOWED: False,
        },
        "diagnoses": [
            {
                "tool": "sdetkit-security-gate",
                "rule_id": "SEC_DEBUG_PRINT",
                "path": "src/sdetkit/reporter.py",
                "line": 22,
                "freshness": "current",
                "classification": "_".join(("safe", "mechanical", "fix", "candidate")),
                "recommended_action": "_".join(("propose", "stdout", "emission", "repair")),
                "fix_proposal": "Replace direct output with explicit stdout emission.",
                "human_review_required": True,
            }
        ],
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        security_finding_diagnosis=security_diagnosis,
    )

    assert "<summary><strong>Security finding diagnosis</strong></summary>" in body
    assert "Current findings: `1`" in body
    assert "Mechanical fix proposals: `1`" in body
    assert "Automatic security fix allowed: `false`" in body
    assert "Automatic dismissal allowed: `false`" in body
    assert "SEC_DEBUG_PRINT" in body
    assert "src/sdetkit/reporter.py:22" in body
    assert "Human review required: `true`" in body
    assert "Replace direct output with explicit stdout emission." in body


def test_write_comment_body_loads_security_diagnosis_artifact_for_operator_visibility(
    tmp_path: Path,
) -> None:
    action_path = _write_json(
        tmp_path / "action-report.json",
        {
            "status": "green",
            "primary_blocker": {},
            "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
            "recommended_actions": [],
            "proof_commands": [],
        },
    )
    intelligence_path = _write_json(
        tmp_path / "check-intelligence.json",
        {
            "checks_seen": 1,
            "failed_checks": [],
            "queued_checks": [],
            "startup_failures": [],
            "security_review": {"collected": True, "unresolved_findings": 0},
        },
    )
    diagnosis_path = _write_json(
        tmp_path / "security-finding-diagnosis.json",
        {
            "collection_status": "collected",
            "summary": {"open_findings": 0, "current_findings": 0, "stale_findings": 0},
            "decision_boundary": {
                report.AUTOMATIC_SECURITY_FIX_ALLOWED: False,
                report.AUTOMATIC_DISMISSAL_ALLOWED: False,
            },
            "diagnoses": [],
        },
    )
    out = tmp_path / "comment.md"

    report.write_comment_body(
        action_report_path=action_path,
        check_intelligence_path=intelligence_path,
        security_finding_diagnosis_path=diagnosis_path,
        out=out,
    )

    body = out.read_text(encoding="utf-8")
    assert "<summary><strong>Security finding diagnosis</strong></summary>" in body
    assert "Open findings: `0`" in body
    assert "Findings: none" in body
    assert "Automatic dismissal allowed: `false`" in body


def test_action_report_renders_verified_prior_disposition_as_advisory_only() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 1,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    security_diagnosis = {
        "collection_status": "collected",
        "summary": {
            "open_findings": 1,
            "current_findings": 1,
            "stale_findings": 0,
            "safe_mechanical_fix_candidates": 1,
            "true_positive_fix_required": 0,
        },
        report.TRUSTED_REVIEWED_DISPOSITION_HISTORY: {
            "status": "verified_v2_read_only",
            "matched_current_findings": 1,
        },
        "decision_boundary": {
            report.AUTOMATIC_SECURITY_FIX_ALLOWED: False,
            report.AUTOMATIC_DISMISSAL_ALLOWED: False,
            report.HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION: False,
        },
        "diagnoses": [
            {
                "tool": "sdetkit-security-gate",
                "rule_id": "SEC_DEBUG_PRINT",
                "path": "src/sdetkit/reporter.py",
                "line": 22,
                "freshness": "current",
                "classification": "safe_mechanical_fix_candidate",
                "recommended_action": "propose_stdout_emission_repair",
                "human_review_required": True,
                report.TRUSTED_REVIEWED_DISPOSITION_CONTEXT: {
                    report.MATCHING_REVIEWED_DISPOSITION_COUNT: 1,
                    "latest_reviewed_reason": "false positive",
                    report.HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION: False,
                },
            }
        ],
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        security_finding_diagnosis=security_diagnosis,
    )

    assert "Trusted reviewed disposition context: `verified_v2_read_only`" in body
    assert "Current findings with verified prior review context: `1`" in body
    assert "Historical disposition authorizes current action: `false`" in body
    assert "Verified prior reviewed dispositions: `1`" in body
    assert "Latest prior reviewed reason: `false positive`" in body
    assert "Prior disposition is advisory evidence only; current action remains manual." in body
    assert "Human review required: `true`" in body


def test_action_report_runtime_lines_render_controlled_history_as_advisory_only() -> None:
    from sdetkit import pr_quality_action_report as report

    lines = report._runtime_proof_artifact_lines(
        {
            "trusted_history": {
                "collection_status": "collected",
                "status": "trusted_history_verified",
                "controlled_validation_record_count": 1,
                "controlled_validation_scenario_count": 2,
                "controlled_structurally_verified_count": 1,
                "controlled_review_first_count": 1,
                "latest_controlled_validation_status": "controlled_validation_passed",
                "controlled_validation_reporting_only": True,
                "controlled_validation_authorizes_current_action": False,
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
            "decision_boundary": {
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        }
    )
    body = "\n".join(lines)

    assert "Trusted history controlled validation records: `1`" in body
    assert "Trusted history controlled validation scenarios: `2`" in body
    assert (
        "Trusted history latest controlled validation status: `controlled_validation_passed`"
        in body
    )
    assert "Trusted history controlled validation reporting only: `true`" in body
    assert "Trusted history controlled validation authorizes current action: `false`" in body
    assert "Automation allowed by trusted history: `false`" in body
    assert "Merge authorized by trusted history: `false`" in body
    assert "Semantic equivalence proven by trusted history: `false`" in body


def test_action_report_comment_renders_job_step_confirmation() -> None:
    action = {
        "status": "review_required",
        "primary_blocker": {
            "check": "Fast CI lane",
            "title": "Type contract drift detected",
            "surface": "quality",
            "code": "MYPY_TYPE_CONTRACT_DRIFT",
            check_intelligence.FAILED_STEP_EVIDENCE_KEY: {
                "status": "found",
                "command": "python -m mypy src",
                "source": "github_actions_group",
                "line_number": 1,
                "failure_line_number": 3,
                "reporting_only": True,
                "automation_allowed": False,
            },
            check_intelligence.JOB_STEP_CONFIRMATION_KEY: {
                "status": "confirmed",
                "source": "github_job_steps",
                "job_step_name": "Run python -m mypy src",
                "job_step_conclusion": "failure",
                "log_command": "python -m mypy src",
                "reporting_only": True,
                "automation_allowed": False,
                "merge_authorized": False,
            },
        },
        "automation": {"attempted": False, "allowed": False, "reason": "review-first"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    body = report.render_comment_body(action_report=action, check_intelligence={})

    assert "Failed step evidence: `found`" in body
    assert "Failed command: `python -m mypy src`" in body
    assert "Job step confirmation: `confirmed`" in body
    assert "GitHub job step: `Run python -m mypy src`" in body
    assert "GitHub job step conclusion: `failure`" in body
    assert "Job step automation allowed: `false`" in body


def test_action_report_comment_renders_artifact_evidence() -> None:
    action = {
        "status": "review_required",
        "primary_blocker": {
            "check": "audit",
            "title": "Dependency audit reported vulnerable packages",
            "surface": "dependency",
            "code": check_intelligence.DEPENDENCY_AUDIT_VULNERABILITY,
            check_intelligence.ARTIFACT_EVIDENCE_KEY: {
                "status": "present",
                "expected_artifacts": ["pip-audit-report.json"],
                "present_artifacts": ["pip-audit-report.json"],
                "missing_artifacts": [],
                "source": "workflow_artifact_url",
                "reporting_only": True,
                "automation_allowed": False,
                "merge_authorized": False,
            },
        },
        "automation": {"attempted": False, "allowed": False, "reason": "review-first"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }

    body = report.render_comment_body(action_report=action, check_intelligence={})

    assert "Artifact evidence: `present`" in body
    assert "Expected artifacts: `pip-audit-report.json`" in body
    assert "Present artifacts: `pip-audit-report.json`" in body
    assert "Artifact evidence source: `workflow_artifact_url`" in body
    assert "Artifact automation allowed: `false`" in body


def test_action_report_security_review_signal_diagnoses_current_findings() -> None:
    high_entropy_rule = "SEC_" + "HIGH_" + "ENTROPY_" + "STRING"
    action = {
        "status": "review_required",
        "primary_blocker": {
            "check": "GitHub security review",
            "title": "Security review requires action",
            "surface": "security",
            "code": "SECURITY_REVIEW_FINDING",
        },
        "automation": {
            "attempted": False,
            "allowed": False,
            "reason": "security review findings are review-first",
        },
        "recommended_actions": ["Review unresolved security comments."],
        "proof_commands": ["python -m sdetkit security check --root . --format json"],
    }
    intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 2},
    }
    evidence_narrative = {
        "quality": {"ok": True, "coverage_percent": "96.69"},
        "primary_signal": {
            "kind": "review_signal",
            "surface": "security",
            "title": "Security review requires action",
        },
        "graph": {
            "node_count": 6,
            "review_first_count": 5,
            "critical_count": 1,
            "top_blocker": {
                "title": "Security review requires action",
                "surface": "security",
                "action": "review",
                "review_first": True,
            },
        },
    }
    security_diagnosis = {
        "summary": {
            report.CURRENT_FINDINGS: 2,
            report.STALE_FINDINGS: 1,
            report.TRUE_POSITIVE_FIX_REQUIRED: 0,
        },
        "decision_boundary": {
            report.AUTOMATIC_DISMISSAL_ALLOWED: False,
            report.AUTOMATIC_SECURITY_FIX_ALLOWED: False,
        },
        "diagnoses": [
            {
                "path": "src/sdetkit/example.py",
                "line": 10,
                "rule_id": high_entropy_rule,
                "freshness": "current",
                "classification": "review_first_security_signal",
                "recommended_action": "manual_security_review",
            }
        ],
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        evidence_narrative=evidence_narrative,
        security_finding_diagnosis=security_diagnosis,
    )

    assert "SDETKit Review Result: Action required" in body
    assert "Current findings: `2`" in body
    assert "Stale findings: `1`" in body
    assert "current PR-owned security findings still need human disposition" in body
    assert "blocked until the current findings are fixed or reviewed as false positives" in body
    assert "Automatic dismissal allowed: `false`" in body
    assert "src/sdetkit/example.py:10" in body
    assert high_entropy_rule in body


def test_action_report_security_review_signal_diagnoses_stale_only_findings() -> None:
    stale_classification = "_".join(("stale", "or", "outdated", "alert"))
    action = {
        "status": "review_required",
        "primary_blocker": {
            "check": "GitHub security review",
            "title": "Security review requires action",
            "surface": "security",
            "code": "SECURITY_REVIEW_FINDING",
        },
        "automation": {
            "attempted": False,
            "allowed": False,
            "reason": "security review findings are review-first",
        },
        "recommended_actions": ["Review unresolved security comments."],
        "proof_commands": ["python -m sdetkit security check --root . --format json"],
    }
    intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 4},
    }
    evidence_narrative = {
        "quality": {"ok": True, "coverage_percent": "96.69"},
        "primary_signal": {
            "kind": "review_signal",
            "surface": "security",
            "title": "Security review requires action",
        },
        "graph": {
            "node_count": 6,
            "review_first_count": 5,
            "critical_count": 1,
            "top_blocker": {
                "title": "Security review requires action",
                "surface": "security",
                "action": "review",
                "review_first": True,
            },
        },
    }
    security_diagnosis = {
        "summary": {
            report.CURRENT_FINDINGS: 0,
            report.STALE_FINDINGS: 4,
            report.TRUE_POSITIVE_FIX_REQUIRED: 0,
        },
        "decision_boundary": {
            report.AUTOMATIC_DISMISSAL_ALLOWED: False,
            report.AUTOMATIC_SECURITY_FIX_ALLOWED: False,
        },
        "diagnoses": [
            {
                "path": "src/sdetkit/example.py",
                "line": 10,
                "rule_id": "SECURITY_REVIEW_FINDING",
                "freshness": "stale",
                "classification": stale_classification,
                "recommended_action": "wait_for_code_scanning_refresh",
            }
        ],
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        evidence_narrative=evidence_narrative,
        security_finding_diagnosis=security_diagnosis,
    )

    assert "Current findings: `0`" in body
    assert "Stale findings: `4`" in body
    assert "stale security review comments remain, but no current findings were reported" in body
    assert "blocked only while stale review comments remain unresolved" in body
    assert "refresh code scanning or resolve stale review comments" in body
    assert "wait_for_code_scanning_refresh" in body


def test_write_comment_body_surfaces_failure_bundle_safety_summary(tmp_path: Path) -> None:
    action_path = _write_json(
        tmp_path / "action-report.json",
        {
            "status": "safe_fix_available",
            "primary_blocker": {},
            "automation": {
                "attempted": False,
                "allowed": True,
                "reason": "safe fix planning is allowed, but not applied by this report",
            },
            "recommended_actions": ["Run the listed proof before any merge decision."],
            "proof_commands": ["python -m pre_commit run -a"],
            "safe_fix_available": True,
        },
    )
    intelligence_path = _write_json(
        tmp_path / "check-intelligence.json",
        {
            "checks_seen": 3,
            "failed_checks": [
                {
                    "name": "ruff",
                    "safe_to_auto_fix": True,
                    "review_first": False,
                    "first_failure": {
                        "line": "I001 Import block is un-sorted or un-formatted",
                        "line_number": 12,
                        "tool": "ruff",
                        "kind": "lint",
                    },
                    "diagnosis": {
                        "owner_files": ["tests/test_widget.py"],
                    },
                }
            ],
            "queued_checks": [],
            "startup_failures": [],
            "missing_required_contexts": [],
        },
    )
    out = tmp_path / "comment.md"
    bundle_out = tmp_path / "failure-bundle"

    result = report.write_comment_body(
        action_report_path=action_path,
        check_intelligence_path=intelligence_path,
        out=out,
        failure_bundle_out_dir=bundle_out,
        pr_number=1606,
        head_sha="head-sha",
        base_sha="base-sha",
    )

    failure_bundle = result["failure_bundle"]
    safety_summary = failure_bundle["safety_summary"]

    assert failure_bundle["out_dir"] == bundle_out.as_posix()
    assert failure_bundle["report_path"] == (bundle_out / "failure-bundle.md").as_posix()
    assert failure_bundle["files"] == [
        (bundle_out / "manifest.json").as_posix(),
        (bundle_out / "failure-bundle.json").as_posix(),
        (bundle_out / "failure-bundle.md").as_posix(),
    ]
    assert safety_summary == {
        "review_first": False,
        "safe_fix_allowed": True,
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }

    markdown = (bundle_out / "failure-bundle.md").read_text(encoding="utf-8")
    assert "# Current-head failure evidence bundle" in markdown
    assert "- Safe fix allowed: `true`" in markdown
    assert "- Review first: `false`" in markdown


def test_action_report_renders_operator_safetygate_summary_without_authority() -> None:
    action = {
        "status": "safe_fix_available",
        "primary_blocker": {},
        "automation": {"allowed": False, "reason": "reporting only"},
        "recommended_actions": ["Review the summary and run required proof."],
        "proof_commands": ["python -m pytest -q tests/test_patch_scorer.py -o addopts="],
        "failure_bundle": {
            "safety_summary": {
                "review_first": False,
                "safe_fix_allowed": True,
                "allowed_files": ["tests/test_patch_scorer.py"],
                "proof_commands": ["python -m pytest -q tests/test_patch_scorer.py -o addopts="],
                "automation_allowed": False,
                "patch_application_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            }
        },
        "patch_score": {
            "score": 100,
            "decision": {
                "status": "candidate_for_protected_verification",
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
            "safety_gate_evidence": {
                "record_count": 1,
                "safe_fix_allowed_count": 1,
                "review_first_count": 0,
                "decision_boundary": {
                    "automation_allowed": False,
                    "patch_application_allowed": False,
                    "merge_authorized": False,
                    "semantic_equivalence_proven": False,
                },
            },
        },
        "protected_verifier_result": {
            "decision": {
                "status": "structurally_verified_candidate",
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
            "safety_gate_evidence": {
                "record_count": 1,
                "decision_boundary": {
                    "automation_allowed": False,
                    "patch_application_allowed": False,
                    "merge_authorized": False,
                    "semantic_equivalence_proven": False,
                },
            },
        },
        "benchmark_report": {
            "safety_gate_evidence": {
                "scenario_count": 1,
                "record_count": 1,
                "decision_boundary": {
                    "automation_allowed": False,
                    "patch_application_allowed": False,
                    "merge_authorized": False,
                    "semantic_equivalence_proven": False,
                },
            }
        },
        "repo_memory": {
            "safety_gate_evidence": {
                "record_count": 1,
                "decision_boundary": {
                    "automation_allowed": False,
                    "patch_application_allowed": False,
                    "merge_authorized": False,
                    "semantic_equivalence_proven": False,
                },
            }
        },
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence={"checks_seen": 1, "failed_checks": []},
        trajectory_records=[
            {
                "safety_gate": {
                    "review_first": False,
                    "safe_fix_allowed": True,
                    "automation_allowed": False,
                    "patch_application_allowed": False,
                    "merge_authorized": False,
                    "semantic_equivalence_proven": False,
                }
            }
        ],
    )

    assert "<summary><strong>Operator SafetyGate summary</strong></summary>" in body
    assert "- Failure bundle safe-fix allowed: `true`" in body
    assert "- Operator summary allowed files: `tests/test_patch_scorer.py`" in body
    assert (
        "- Operator summary proof commands: "
        "`python -m pytest -q tests/test_patch_scorer.py -o addopts=`" in body
    )
    assert "- Trajectory SafetyGate records: `1`" in body
    assert "- RepoMemory SafetyGate records: `1`" in body
    assert "- Replay benchmark SafetyGate scenarios: `1`" in body
    assert "- PatchScorer status: `candidate_for_protected_verification`" in body
    assert "- PatchScorer score: `100`" in body
    assert "- ProtectedVerifier status: `structurally_verified_candidate`" in body
    assert (
        "- Operator next action: `Human review may use this evidence, but no automation or merge authority is granted.`"
        in body
    )
    assert "- Operator summary automation allowed: `false`" in body
    assert "- Operator summary patch application allowed: `false`" in body
    assert "- Operator summary merge authorized: `false`" in body
    assert "- Operator summary semantic equivalence proven: `false`" in body


def test_action_report_operator_safetygate_summary_surfaces_authority_expansion() -> None:
    action = {
        "status": "review_first",
        "primary_blocker": {},
        "automation": {"allowed": False, "reason": "reporting only"},
        "recommended_actions": ["Keep review-first."],
        "proof_commands": [],
        "patch_score": {
            "score": 0,
            "decision": {
                "status": "blocked_review_first",
                "automation_allowed": False,
            },
            "safety_gate_evidence": {
                "decision_boundary": {
                    "automation_allowed": True,
                    "patch_application_allowed": False,
                    "merge_authorized": False,
                    "semantic_equivalence_proven": False,
                }
            },
        },
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence={"checks_seen": 1, "failed_checks": []},
    )

    assert "<summary><strong>Operator SafetyGate summary</strong></summary>" in body
    assert (
        "- Operator next action: `Review-first: a SafetyGate boundary attempted to expand authority.`"
        in body
    )
    assert "- Operator summary automation allowed: `true`" in body
    assert "- Operator summary merge authorized: `false`" in body


def test_action_report_green_comment_collapses_operator_sections_by_default() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 12,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        evidence_narrative={"quality": {"ok": True}},
    )

    assert "<summary><strong>Primary blocker</strong></summary>" in body
    assert "<summary><strong>Failed check diagnoses</strong></summary>" in body
    assert "<details open>" not in body
    assert "No action required from SDETKit." in body


def test_action_report_failure_comment_expands_operator_action_sections() -> None:
    action = {
        "status": "review_required",
        "primary_blocker": {
            "check": "ruff",
            "title": "Ruff lint contract failed",
            "surface": "quality",
            "code": "RUFF_LINT_FAILURE",
            "impact": "CI is blocked by a lint finding.",
            "path": "src/sdetkit/check_intelligence.py",
        },
        "automation": {
            "attempted": False,
            "allowed": False,
            "reason": "diagnosis is review-first",
        },
        "recommended_actions": ["Fix the lint finding."],
        "proof_commands": ["python -m ruff check src tests"],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 1,
        "failed_checks": [
            {
                "name": "ruff",
                "safe_to_auto_fix": False,
                "diagnosis": {
                    "code": "RUFF_LINT_FAILURE",
                    "title": "Ruff lint contract failed",
                },
            }
        ],
        "queued_checks": [],
        "startup_failures": [],
    }

    body = report.render_comment_body(action_report=action, check_intelligence=intelligence)

    assert "<details open>" in body
    assert "<summary><strong>Primary blocker</strong></summary>" in body
    assert "<summary><strong>Failed check diagnoses</strong></summary>" in body
    assert "<summary><strong>Recommended actions</strong></summary>" in body
    assert "Ruff lint contract failed" in body
    assert "Fix the lint finding." in body
    assert "python -m ruff check src tests" in body


def test_pr_quality_comment_v2_collapses_noisy_product_sections() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    evidence_narrative = {
        "quality": {"ok": True, "coverage_percent": "96.69%"},
        "primary_signal": {
            "kind": "review_signal",
            "surface": "workflow",
            "title": "Workflow evidence changed",
        },
        "graph": {
            "node_count": 1,
            "review_first_count": 0,
            "critical_count": 0,
            "top_blocker": {
                "title": "Workflow evidence changed",
                "surface": "workflow",
                "action": "rerun_proof",
                "review_first": False,
            },
        },
        "next_proof": ["python -m pre_commit run -a"],
    }
    security_diagnosis = {
        "collection_status": "collected",
        "summary": {
            "open_findings": 52,
            "current_findings": 0,
            "stale_findings": 52,
        },
        "diagnoses": [
            {
                "rule_id": "CVE-EXAMPLE",
                "path": "tests/fixtures/example.txt",
                "line": 1,
                "tool": "osv-scanner",
                "freshness": "stale",
                "classification": "stale_or_outdated_alert",
                "recommended_action": "wait_for_code_scanning_refresh",
                "human_review_required": True,
            }
        ],
        "decision_boundary": {
            "automatic_security_fix_allowed": False,
            "automatic_dismissal_allowed": False,
        },
    }
    runtime_proof = {
        "status": "collected",
        "isolated_proof": {
            "status": "passed",
            "git_inventory_verified": True,
            "runtime_guard_checked": True,
            "runtime_guard_passed": True,
        },
        "decision_boundary": {
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        evidence_narrative=evidence_narrative,
        security_finding_diagnosis=security_diagnosis,
        runtime_proof_artifacts=runtime_proof,
    )

    assert "## Quality summary" in body
    assert "## Evidence proof signal" in body
    assert "## Merge assessment" in body

    assert "<summary><strong>Security finding diagnosis</strong></summary>" in body
    assert "<summary><strong>Runtime proof artifacts</strong></summary>" in body
    assert "<summary><strong>Primary blocker</strong></summary>" in body
    assert "<summary><strong>Automation decision</strong></summary>" in body
    assert "<summary><strong>Evidence collected</strong></summary>" in body
    assert "<summary><strong>Required proof</strong></summary>" in body

    assert "## Security finding diagnosis" not in body
    assert "## Runtime proof artifacts" not in body
    assert "## Primary blocker" not in body
    assert "## Automation decision" not in body


def test_pr_quality_comment_v3_renders_reviewer_dashboard_top_card() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    evidence_narrative = {
        "quality": {"ok": True, "coverage_percent": "96.69%"},
        "primary_signal": {
            "kind": "review_signal",
            "surface": "workflow",
            "title": "Workflow evidence changed",
        },
        "graph": {
            "node_count": 1,
            "review_first_count": 0,
            "critical_count": 0,
            "top_blocker": {
                "title": "Workflow evidence changed",
                "surface": "workflow",
                "action": "rerun_proof",
                "review_first": False,
            },
        },
        "next_proof": ["python -m pre_commit run -a"],
    }

    body = report.render_comment_body(
        action_report=action,
        check_intelligence=intelligence,
        evidence_narrative=evidence_narrative,
    )

    assert "## Reviewer dashboard" in body
    assert "## Reviewer dashboard" in body.split("## Quality summary", maxsplit=1)[0]
    assert "### Decision" in body
    assert "| SDETKit status | `green` |" in body
    assert "| Merge assessment | `verify_listed_proof_before_routine_merge` |" in body
    assert "| Next reviewer action | `rerun_proof` |" in body
    assert "| Changed risk surface | `workflow` |" in body
    assert "| Signal title | Workflow evidence changed |" in body
    assert "| Review-first evidence | `false` |" in body
    assert "| Failed checks | `0` |" in body
    assert "| Required queued checks | `0` |" in body
    assert "| Required startup failures | `0` |" in body
    assert "| Missing required contexts | `0` |" in body
    assert "### Proof to rerun" in body
    assert "```bash" in body
    assert "python -m pre_commit run -a" in body
    assert "### Authority boundary" in body
    assert "| Boundary mode | `reporting_only` |" in body
    assert "| Patch automation | `false` |" in body
    assert "| Security dismissal | `false` |" in body
    assert "| Merge authorization | `false` |" in body
    assert "| Semantic equivalence claim | `false` |" in body


def test_pr_quality_review_model_is_structured_product_surface() -> None:
    action = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    evidence_narrative = {
        "quality": {"ok": True, "coverage_percent": "96.69%"},
        "primary_signal": {
            "kind": "review_signal",
            "surface": "diagnostic_engine",
            "title": "Diagnostic intelligence evidence changed",
        },
        "graph": {
            "node_count": 1,
            "review_first_count": 0,
            "critical_count": 0,
            "top_blocker": {
                "title": "Diagnostic intelligence evidence changed",
                "surface": "diagnostic_engine",
                "action": "rerun_proof",
                "review_first": False,
            },
        },
        "next_proof": [
            "python -m pytest -q tests/test_adaptive_quality_gate_advisory_alignment.py tests/test_adaptive_failure_bundle.py -o addopts=",
            "python -m pre_commit run -a",
        ],
    }
    heading, signal_lines, review_required = report._evidence_signal(evidence_narrative)

    model = report.build_pr_quality_review_model(
        status="green",
        evidence_signal_heading=heading,
        evidence_signal_lines=signal_lines,
        evidence_review_required=review_required,
        action_report=action,
        check_intelligence=intelligence,
        evidence_narrative=evidence_narrative,
    )

    assert model["schema_version"] == "sdetkit.pr_quality.review_model.v1"
    assert model["decision"] == {
        "status": "green",
        "merge_assessment": "verify_listed_proof_before_routine_merge",
        "next_action": "rerun_proof",
        "risk_surface": "diagnostic_engine",
        "signal_title": "Diagnostic intelligence evidence changed",
        "comment_signal": "Evidence proof signal",
        "review_first_evidence": False,
        "failed_checks": 0,
        "required_queued_checks": 0,
        "required_startup_failures": 0,
        "missing_required_contexts": 0,
        "cleared_security_signal": False,
    }
    assert model["proof_to_rerun"] == [
        "python -m pytest -q tests/test_adaptive_quality_gate_advisory_alignment.py tests/test_adaptive_failure_bundle.py -o addopts=",
        "python -m pre_commit run -a",
    ]
    assert model["authority_boundary"] == {
        "boundary_mode": "reporting_only",
        "patch_automation": False,
        "security_dismissal": False,
        "merge_authorization": False,
        "semantic_equivalence_claim": False,
    }


def test_write_comment_body_writes_review_model_artifact(tmp_path: Path) -> None:
    action_report_path = tmp_path / "action-report.json"
    check_intelligence_path = tmp_path / "check-intelligence.json"
    evidence_narrative_path = tmp_path / "evidence-narrative.json"
    comment_out = tmp_path / "comment.md"
    review_model_out = tmp_path / "review-model.json"

    action_report = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    check_intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    evidence_narrative = {
        "quality": {"ok": True, "coverage_percent": "96.69%"},
        "primary_signal": {
            "kind": "review_signal",
            "surface": "diagnostic_engine",
            "title": "Diagnostic intelligence evidence changed",
        },
        "graph": {
            "node_count": 1,
            "review_first_count": 0,
            "critical_count": 0,
            "top_blocker": {
                "title": "Diagnostic intelligence evidence changed",
                "surface": "diagnostic_engine",
                "action": "rerun_proof",
                "review_first": False,
            },
        },
        "next_proof": [
            "python -m pytest -q tests/test_adaptive_quality_gate_advisory_alignment.py tests/test_adaptive_failure_bundle.py -o addopts=",
            "python -m pre_commit run -a",
        ],
    }

    action_report_path.write_text(
        json.dumps(action_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    check_intelligence_path.write_text(
        json.dumps(check_intelligence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    evidence_narrative_path.write_text(
        json.dumps(evidence_narrative, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = report.write_comment_body(
        action_report_path=action_report_path,
        check_intelligence_path=check_intelligence_path,
        evidence_narrative_path=evidence_narrative_path,
        out=comment_out,
        review_model_out=review_model_out,
    )

    assert result["review_model_written"] is True
    assert result["review_model_out"] == review_model_out.as_posix()
    assert result["review_model_schema_version"] == "sdetkit.pr_quality.review_model.v1"

    model = json.loads(review_model_out.read_text(encoding="utf-8"))
    assert model["schema_version"] == "sdetkit.pr_quality.review_model.v1"
    assert model["decision"]["merge_assessment"] == "verify_listed_proof_before_routine_merge"
    assert model["decision"]["next_action"] == "rerun_proof"
    assert model["decision"]["risk_surface"] == "diagnostic_engine"
    assert model["proof_to_rerun"] == [
        "python -m pytest -q tests/test_adaptive_quality_gate_advisory_alignment.py tests/test_adaptive_failure_bundle.py -o addopts=",
        "python -m pre_commit run -a",
    ]
    assert model["authority_boundary"] == {
        "boundary_mode": "reporting_only",
        "merge_authorization": False,
        "patch_automation": False,
        "security_dismissal": False,
        "semantic_equivalence_claim": False,
    }

    body = comment_out.read_text(encoding="utf-8")
    assert "## Reviewer dashboard" in body
    assert "### Proof to rerun" in body


def test_write_comment_body_writes_review_summary_artifact(tmp_path: Path) -> None:
    action_report_path = tmp_path / "action-report.json"
    check_intelligence_path = tmp_path / "check-intelligence.json"
    evidence_narrative_path = tmp_path / "evidence-narrative.json"
    comment_out = tmp_path / "comment.md"
    review_model_out = tmp_path / "review-model.json"
    review_summary_out = tmp_path / "review-summary.md"

    action_report = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    check_intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    evidence_narrative = {
        "quality": {"ok": True, "coverage_percent": "96.69%"},
        "primary_signal": {
            "kind": "review_signal",
            "surface": "diagnostic_engine",
            "title": "Diagnostic intelligence evidence changed",
        },
        "graph": {
            "node_count": 1,
            "review_first_count": 0,
            "critical_count": 0,
            "top_blocker": {
                "title": "Diagnostic intelligence evidence changed",
                "surface": "diagnostic_engine",
                "action": "rerun_proof",
                "review_first": False,
            },
        },
        "next_proof": [
            "python -m pytest -q tests/test_adaptive_quality_gate_advisory_alignment.py tests/test_adaptive_failure_bundle.py -o addopts=",
            "python -m pre_commit run -a",
        ],
    }

    action_report_path.write_text(
        json.dumps(action_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    check_intelligence_path.write_text(
        json.dumps(check_intelligence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    evidence_narrative_path.write_text(
        json.dumps(evidence_narrative, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = report.write_comment_body(
        action_report_path=action_report_path,
        check_intelligence_path=check_intelligence_path,
        evidence_narrative_path=evidence_narrative_path,
        out=comment_out,
        review_model_out=review_model_out,
        review_summary_out=review_summary_out,
    )

    assert result["review_model_written"] is True
    assert result["review_summary_written"] is True
    assert result["review_summary_out"] == review_summary_out.as_posix()

    summary = review_summary_out.read_text(encoding="utf-8")
    assert "# PR Quality Review Summary" in summary
    assert "| Merge assessment | `verify_listed_proof_before_routine_merge` |" in summary
    assert "| Next action | `rerun_proof` |" in summary
    assert "| Risk surface | `diagnostic_engine` |" in summary
    assert "```bash" in summary
    assert "python -m pre_commit run -a" in summary
    assert "| Boundary mode | `reporting_only` |" in summary
    assert "| Merge authorization | `false` |" in summary
    assert "does not authorize merge" in summary


def test_write_comment_body_writes_review_html_dashboard_artifact(tmp_path: Path) -> None:
    action_report_path = tmp_path / "action-report.json"
    check_intelligence_path = tmp_path / "check-intelligence.json"
    evidence_narrative_path = tmp_path / "evidence-narrative.json"
    comment_out = tmp_path / "comment.md"
    review_model_out = tmp_path / "review-model.json"
    review_summary_out = tmp_path / "review-summary.md"
    review_html_out = tmp_path / "review-dashboard.html"

    action_report = {
        "status": "green",
        "primary_blocker": {},
        "automation": {"attempted": False, "allowed": False, "reason": "no remediation needed"},
        "recommended_actions": [],
        "proof_commands": [],
        "evidence": {},
    }
    check_intelligence = {
        "checks_seen": 44,
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "security_review": {"collected": True, "unresolved_findings": 0},
    }
    evidence_narrative = {
        "quality": {"ok": True, "coverage_percent": "96.69%"},
        "primary_signal": {
            "kind": "review_signal",
            "surface": "diagnostic_engine",
            "title": "Diagnostic intelligence evidence changed",
        },
        "graph": {
            "node_count": 1,
            "review_first_count": 0,
            "critical_count": 0,
            "top_blocker": {
                "title": "Diagnostic intelligence evidence changed",
                "surface": "diagnostic_engine",
                "action": "rerun_proof",
                "review_first": False,
            },
        },
        "next_proof": ["python -m pre_commit run -a"],
    }

    action_report_path.write_text(
        json.dumps(action_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    check_intelligence_path.write_text(
        json.dumps(check_intelligence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    evidence_narrative_path.write_text(
        json.dumps(evidence_narrative, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = report.write_comment_body(
        action_report_path=action_report_path,
        check_intelligence_path=check_intelligence_path,
        evidence_narrative_path=evidence_narrative_path,
        out=comment_out,
        review_model_out=review_model_out,
        review_summary_out=review_summary_out,
        review_html_out=review_html_out,
    )

    assert result["review_html_written"] is True
    assert result["review_html_out"] == review_html_out.as_posix()

    html = review_html_out.read_text(encoding="utf-8")
    assert "<!doctype html>" in html
    assert "<title>PR Quality Review Dashboard</title>" in html
    assert "<h1>PR Quality Review Dashboard</h1>" in html
    assert "verify_listed_proof_before_routine_merge" in html
    assert "rerun_proof" in html
    assert "python -m pre_commit run -a" in html
    assert "Reporting-only" in html
    assert "does not authorize merge" in html
