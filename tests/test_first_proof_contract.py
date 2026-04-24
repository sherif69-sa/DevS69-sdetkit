from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

SCRIPT = Path("scripts/check_first_proof_summary_contract.py").resolve()


def _run(summary_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--summary", str(summary_path), "--format", "json"],
        check=False,
        text=True,
        capture_output=True,
    )


def test_first_proof_contract_ok(tmp_path: Path) -> None:
    summary_path = tmp_path / "first-proof-summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "ok": True,
                "decision": "SHIP",
                "decision_line": "FIRST_PROOF_DECISION=SHIP",
                "strict": False,
                "selected_python": "/usr/bin/python3.11",
                "failed_steps": [],
                "steps": [
                    {
                        "name": "gate-fast",
                        "command": ["python", "-m", "sdetkit", "gate", "fast"],
                        "returncode": 0,
                        "stdout_log": "a.stdout.log",
                        "stderr_log": "a.stderr.log",
                        "artifact": "a.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    proc = _run(summary_path)
    assert proc.returncode == 0
    result = json.loads(proc.stdout)
    assert result["ok"] is True


def test_first_proof_contract_detects_mismatch(tmp_path: Path) -> None:
    summary_path = tmp_path / "first-proof-summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "ok": True,
                "decision": "SHIP",
                "decision_line": "FIRST_PROOF_DECISION=SHIP",
                "strict": True,
                "selected_python": "/usr/bin/python3.11",
                "failed_steps": [],
                "steps": [
                    {
                        "name": "doctor",
                        "command": ["python", "-m", "sdetkit", "doctor"],
                        "returncode": 1,
                        "stdout_log": "doctor.stdout.log",
                        "stderr_log": "doctor.stderr.log",
                        "artifact": "doctor.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    proc = _run(summary_path)
    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    errors = result["errors"]
    assert any("failed_steps must match" in row for row in errors)
    assert any("ok must be true only" in row for row in errors)


def test_first_proof_contract_missing_summary_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--summary",
            str(missing_path),
            "--wait-seconds",
            "0",
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result["ok"] is False
    assert any("unable to load summary:" in row for row in result["errors"])


def test_first_proof_contract_allow_missing_summary_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--summary",
            str(missing_path),
            "--allow-missing",
            "--wait-seconds",
            "0",
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert result["skipped"] is True


def test_first_proof_contract_waits_for_stale_file_refresh(tmp_path: Path) -> None:
    summary_path = tmp_path / "first-proof-summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "ok": True,
                "strict": False,
                "selected_python": "/usr/bin/python3.11",
                "failed_steps": [],
                "steps": [],
            }
        ),
        encoding="utf-8",
    )

    def _rewrite_valid() -> None:
        time.sleep(0.2)
        summary_path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "decision": "SHIP",
                    "decision_line": "FIRST_PROOF_DECISION=SHIP",
                    "strict": False,
                    "selected_python": "/usr/bin/python3.11",
                    "failed_steps": [],
                    "steps": [],
                }
            ),
            encoding="utf-8",
        )

    t = threading.Thread(target=_rewrite_valid, daemon=True)
    t.start()
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--summary",
            str(summary_path),
            "--wait-seconds",
            "2",
            "--wait-interval",
            "0.1",
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    t.join(timeout=1.0)
    assert proc.returncode == 0
    result = json.loads(proc.stdout)
    assert result["ok"] is True


def test_first_proof_contract_detects_decision_line_mismatch(tmp_path: Path) -> None:
    summary_path = tmp_path / "first-proof-summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "ok": True,
                "decision": "SHIP",
                "decision_line": "FIRST_PROOF_DECISION=NO-SHIP",
                "strict": False,
                "selected_python": "/usr/bin/python3.11",
                "failed_steps": [],
                "steps": [],
            }
        ),
        encoding="utf-8",
    )
    proc = _run(summary_path)
    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert any("decision_line must match computed SHIP/NO-SHIP outcome" in row for row in result["errors"])
