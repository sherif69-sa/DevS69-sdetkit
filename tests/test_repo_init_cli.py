from __future__ import annotations

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


def test_repo_init_dry_run_does_not_write_files(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    proc = _run_cli(
        repo_root,
        tmp_path,
        "repo",
        "init",
        "--preset",
        "enterprise_python",
        "--dry-run",
    )

    assert proc.returncode == 0, proc.stderr
    assert "CREATE SECURITY.md" in proc.stdout
    assert "CREATE .github/workflows/ci.yml" in proc.stdout
    assert not (tmp_path / "SECURITY.md").exists()
    assert not (tmp_path / ".github").exists()


def test_repo_init_creates_expected_files(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    proc = _run_cli(
        repo_root,
        tmp_path,
        "repo",
        "init",
        "--preset",
        "enterprise_python",
    )

    assert proc.returncode == 0, proc.stderr
    expected = [
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "LICENSE",
        "CODEOWNERS",
        ".github/workflows/ci.yml",
        ".github/workflows/quality.yml",
        ".github/workflows/security.yml",
    ]
    for rel in expected:
        assert (tmp_path / rel).exists()


def test_repo_apply_adds_missing_and_skips_existing_without_force(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    custom_security = "custom policy\n"
    (tmp_path / "SECURITY.md").write_text(custom_security, encoding="utf-8")

    proc = _run_cli(
        repo_root,
        tmp_path,
        "repo",
        "apply",
        "--preset",
        "enterprise_python",
    )

    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "SECURITY.md").read_text(encoding="utf-8") == custom_security
    assert (tmp_path / ".github/workflows/ci.yml").exists()

    force_proc = _run_cli(
        repo_root,
        tmp_path,
        "repo",
        "apply",
        "--preset",
        "enterprise_python",
        "--force",
    )
    assert force_proc.returncode == 0, force_proc.stderr
    assert (tmp_path / "SECURITY.md").read_text(encoding="utf-8") != custom_security
