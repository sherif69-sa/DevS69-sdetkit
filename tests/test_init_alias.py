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


def test_root_init_alias_defaults_to_enterprise_preset(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    proc = _run_cli(
        repo_root,
        tmp_path,
        "init",
        "--dry-run",
        "--format",
        "json",
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout[proc.stdout.find("{") :])
    assert payload["schema_version"] == "sdetkit.repo-init.v1"
    assert payload["preset"] == "enterprise_python"


def test_repo_init_write_config_creates_sdetkit_config(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    proc = _run_cli(
        repo_root,
        tmp_path,
        "repo",
        "init",
        "--preset",
        "enterprise_python",
        "--write-config",
    )
    assert proc.returncode == 0, proc.stderr
    cfg = tmp_path / ".sdetkit" / "config.toml"
    assert cfg.exists()
    text = cfg.read_text(encoding="utf-8")
    assert 'default_profile = "default"' in text
