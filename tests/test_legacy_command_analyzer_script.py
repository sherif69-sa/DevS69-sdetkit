from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, str(repo_root / "scripts/legacy_command_analyzer.py"), *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env={"PYTHONPATH": str(repo_root / "src")},
    )


def test_legacy_command_analyzer_finds_legacy_command_usage(tmp_path: Path) -> None:
    (tmp_path / "ci.sh").write_text("python -m sdetkit phase1-hardening\n", encoding="utf-8")
    proc = _run(tmp_path, "--root", str(tmp_path), "--format", "json")
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["overall_ok"] is False
    assert payload["count"] >= 1
    first = payload["findings"][0]
    assert first["command"] == "phase1-hardening"
    assert "playbooks" in first["preferred_surface"]
