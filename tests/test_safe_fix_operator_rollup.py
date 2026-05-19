from __future__ import annotations

import json
from pathlib import Path

from sdetkit import safe_fix_operator_rollup


def test_operator_rollup_summarizes_pushed_safe_fix() -> None:
    payload = {
        "failed_checks": [
            {
                "name": "autopilot",
                "safe_to_auto_fix": True,
            }
        ],
        "safe_fix_outcome": {
            "status": "pushed",
            "attempted": True,
            "remediation_ok": True,
            "committed": True,
            "pushed": True,
            "affected_files": ["tests/test_example.py"],
            "reason": "PR Quality safe-remediation bridge executed",
        },
    }

    rollup = safe_fix_operator_rollup.build_rollup(payload)

    assert rollup["status"] == "pushed"
    assert rollup["attempted_count"] == 1
    assert rollup["committed_count"] == 1
    assert rollup["pushed_count"] == 1
    assert rollup["safe_candidate_count"] == 1
    assert rollup["review_first_blocker_count"] == 0
    assert rollup["recurring_files"] == [{"path": "tests/test_example.py", "count": 1}]
    assert rollup["recommendation"]["action"] == "rerun_proof"


def test_operator_rollup_reports_review_first_refusal_reason() -> None:
    payload = {
        "failed_checks": [
            {
                "name": "ci",
                "safe_to_auto_fix": False,
            },
            {
                "name": "autopilot",
                "safe_to_auto_fix": True,
            },
        ],
        "safe_fix_outcome": {
            "status": "not_attempted",
            "attempted": False,
            "committed": False,
            "pushed": False,
            "reason": "one or more failed checks are review-first or lack affected files",
        },
    }

    rollup = safe_fix_operator_rollup.build_rollup(payload)

    assert rollup["status"] == "blocked_by_review_first"
    assert rollup["safe_candidate_count"] == 1
    assert rollup["review_first_blocker_count"] == 1
    assert rollup["refusal_count"] == 1
    assert rollup["refusal_reasons"] == [
        {
            "reason": "one or more failed checks are review-first or lack affected files",
            "count": 1,
        }
    ]
    assert rollup["recommendation"]["action"] == "review_blockers"


def test_operator_rollup_writes_json_and_markdown(tmp_path: Path) -> None:
    payload = {
        "safe_fix_outcome": {
            "status": "not_attempted",
            "attempted": False,
            "reason": "no failed checks to remediate",
        }
    }

    rollup = safe_fix_operator_rollup.write_rollup(payload, tmp_path)

    assert rollup["status"] == "blocked_by_review_first"
    json_payload = json.loads((tmp_path / "safe-fix-outcome-rollup.json").read_text())
    assert json_payload["schema_version"] == safe_fix_operator_rollup.SCHEMA_VERSION

    markdown = (tmp_path / "safe-fix-outcome-rollup.md").read_text(encoding="utf-8")
    assert "# Operator safe-fix outcome rollup" in markdown
    assert "no failed checks to remediate" in markdown
