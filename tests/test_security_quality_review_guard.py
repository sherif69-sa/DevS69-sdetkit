from __future__ import annotations

import json
import subprocess
import sys


def test_security_quality_review_guard_plan_mode_emits_report(tmp_path) -> None:
    report = tmp_path / "guard.json"
    proc = subprocess.run(
        [sys.executable, "scripts/security_quality_review_guard.py", "--report", str(report)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "security-quality-review-guard plan:" in proc.stdout
    assert "repo check --format json --out build/repo-check-default.json --force" in proc.stdout
    assert (
        "repo check --profile enterprise --format json --out build/repo-check-enterprise.json --force"
        in proc.stdout
    )
    assert "ruff check src tests" in proc.stdout

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["run"] is False
    assert len(payload["checks"]) == 3
