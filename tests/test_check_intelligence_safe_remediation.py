from __future__ import annotations

import json
from pathlib import Path

from sdetkit import check_intelligence


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_check_intelligence_marks_formatting_failure_safe_to_auto_fix(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "check-runs.json",
        {
            "check_runs": [
                {
                    "name": "autopilot",
                    "status": "completed",
                    "conclusion": "failure",
                    "output": "\n".join(
                        [
                            "ruff format..............................Failed",
                            "- hook id: ruff-format",
                            "- files were modified by this hook",
                            "1 file reformatted",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    failed = intelligence["failed_checks"][0]

    assert failed["safe_to_auto_fix"] is True
    assert failed["safe_remediation"]["strategy"] == "run_pre_commit"
    assert failed["safe_remediation"]["category"] == "formatting_only"


def test_check_intelligence_keeps_type_failure_review_first(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "check-runs.json",
        {
            "check_runs": [
                {
                    "name": "ci",
                    "status": "completed",
                    "conclusion": "failure",
                    "output": "src/sdetkit/example.py:10: error: Incompatible return value type\n",
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    failed = intelligence["failed_checks"][0]

    assert failed["safe_to_auto_fix"] is False
    assert failed["safe_remediation"]["strategy"] == "review_first"
