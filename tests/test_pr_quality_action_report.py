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

    assert "SDETKit Review Result: Green" in body
    assert "## Evidence review signal" in body
    assert "Review signal: `present`" in body
    assert "Surface: `workflow`" in body
    assert "Required checks are not complete" in body
    assert "Operator action: `review`" in body
    assert "`gh pr checks --required`" in body
    assert "Evidence review signal present; review the listed surface before merge." in body
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

    assert "SDETKit Review Result: Green" in body
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
    assert "Evidence review signal present; review the listed surface before merge." not in body
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
    assert "## Evidence review signal" in body
    assert "Review signal: `present`" in body
    assert "Surface: `workflow`" in body
    assert "Required checks are not complete" in body
    assert "Operator action: `review`" in body
    assert "`gh pr checks --required`" in body
    assert "Evidence review signal present; review the listed surface before merge." in body
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
    assert "Evidence review signal present; review the listed surface before merge." not in body
    assert "No action required from SDETKit." not in body
