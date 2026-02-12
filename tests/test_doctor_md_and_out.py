from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run_doctor(repo_root: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    return subprocess.run(
        [sys.executable, "-m", "sdetkit.doctor", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_doctor_markdown_contains_table_actions_and_stable_order(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    proc = _run_doctor(repo_root, tmp_path, "--format", "md", "--ci")

    assert proc.returncode == 2
    assert "### SDET Doctor Report" in proc.stdout
    assert "| Check | Severity | Status | Summary |" in proc.stdout
    assert "#### Action items" in proc.stdout
    assert "#### Evidence" in proc.stdout

    ci_idx = proc.stdout.index("| `ci_workflows` | high | FAIL |")
    sec_idx = proc.stdout.index("| `security_files` | medium | FAIL |")
    assert ci_idx < sec_idx

    action_ci_idx = proc.stdout.index("- `ci_workflows`: Add minimal CI workflow")
    action_sec_idx = proc.stdout.index("- `security_files`: Add SECURITY.md")
    assert action_ci_idx < action_sec_idx


def test_doctor_json_out_writes_file_and_stdout_is_json(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    out_path = tmp_path / "doctor.json"
    proc = _run_doctor(repo_root, tmp_path, "--format", "json", "--out", str(out_path))

    assert proc.returncode == 0
    stdout_payload = json.loads(proc.stdout)
    assert isinstance(stdout_payload, dict)
    assert out_path.exists()

    file_payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert isinstance(file_payload, dict)
    assert stdout_payload["score"] == file_payload["score"]
