from __future__ import annotations

import json
from pathlib import Path

from sdetkit import safe_fix_outcome


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_safe_fix_outcome_builds_visible_push_summary(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "pr-quality-safe-remediation-bridge.json",
        {
            "attempted": True,
            "remediation_ok": True,
            "commit_ok": True,
            "commit_pushed": True,
            "commit_sha": "abc123",
            "affected_files": ["tests/test_example.py"],
            "reason": "PR Quality safe-remediation bridge executed",
        },
    )
    _write_json(
        tmp_path / "safe-fix-plan.json",
        {
            "safe_to_auto_fix": True,
            "fix_type": "format_only",
            "affected_files": ["tests/test_example.py"],
            "proof_commands": ["python -m pre_commit run -a"],
        },
    )
    _write_json(
        tmp_path / "adaptive-safe-remediation-result.json",
        {
            "ok": True,
            "commands": [
                {
                    "command": "python -m pre_commit run -a",
                    "ok": True,
                    "returncode": 0,
                }
            ],
        },
    )

    outcome = safe_fix_outcome.write_outcome(tmp_path)

    assert outcome["status"] == "pushed"
    assert outcome["attempted"] is True
    assert outcome["remediation_ok"] is True
    assert outcome["committed"] is True
    assert outcome["pushed"] is True
    assert outcome["commit_sha"] == "abc123"
    assert outcome["affected_files"] == ["tests/test_example.py"]
    assert outcome["proof_commands"] == ["python -m pre_commit run -a"]

    markdown = (tmp_path / "safe-fix-outcome.md").read_text(encoding="utf-8")
    assert "Safe fix outcome" in markdown
    assert "Commit SHA: `abc123`" in markdown
    assert "`tests/test_example.py`" in markdown


def test_safe_fix_outcome_records_not_attempted_state(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "pr-quality-safe-remediation-bridge.json",
        {
            "attempted": False,
            "reason": "no failed checks to remediate",
        },
    )

    outcome = safe_fix_outcome.write_outcome(tmp_path)

    assert outcome["status"] == "not_attempted"
    assert outcome["attempted"] is False
    assert outcome["committed"] is False
    assert outcome["pushed"] is False
    assert outcome["commit_sha"] == "none"
    assert outcome["reason"] == "no failed checks to remediate"
