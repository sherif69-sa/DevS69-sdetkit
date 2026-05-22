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
    assert "## Review-first patch plan" in body
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

    assert "## Safe fix outcome" in body
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

    assert "## Trajectory summary" in body
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
    assert "## Trajectory summary" in body
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
    assert "## Trajectory summary" in out.read_text(encoding="utf-8")


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
