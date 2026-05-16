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
