from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run_cli(root: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_repo_init_json_emits_detection_and_profile(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "noxfile.py").write_text("import nox\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)

    proc = _run_cli(
        repo_root,
        tmp_path,
        "repo",
        "init",
        "--preset",
        "enterprise_python",
        "--dry-run",
        "--format",
        "json",
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    start = out.find("{")
    payload = json.loads(out[start:])
    assert payload["schema_version"] == "sdetkit.repo-init.v1"
    assert payload["recommended_profile"] in {"standard", "strict", "quick"}
    assert payload["detected"]["has_pyproject"] is True
    assert payload["detected"]["has_tests"] is True


def test_repo_init_text_emits_adoption_summary(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    proc = _run_cli(
        repo_root,
        tmp_path,
        "repo",
        "init",
        "--preset",
        "enterprise_python",
        "--dry-run",
        "--format",
        "text",
    )
    assert proc.returncode == 0, proc.stderr
    assert "repo init adoption summary" in proc.stdout
    assert "recommended profile:" in proc.stdout
    assert "next:" in proc.stdout
