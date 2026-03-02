from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run_sdetkit(repo_root: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_ci_validate_templates_passes_in_repo_strict_json() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    proc = _run_sdetkit(
        repo_root,
        repo_root,
        "ci",
        "validate-templates",
        "--format",
        "json",
        "--strict",
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data.get("ok") is True
    checked = data.get("checked")
    assert isinstance(checked, list)
    ids = {item.get("id") for item in checked if isinstance(item, dict)}
    assert {"gitlab", "jenkins", "tekton"}.issubset(ids)


def test_ci_validate_templates_missing_file_fails(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    (tmp_path / "templates" / "ci" / "gitlab").mkdir(parents=True)
    (tmp_path / "templates" / "ci" / "jenkins").mkdir(parents=True)
    (tmp_path / "templates" / "ci" / "tekton").mkdir(parents=True)

    (tmp_path / "templates" / "ci" / "gitlab" / "day66-advanced-reference.yml").write_text(
        "stages: [test]\n", encoding="utf-8"
    )
    (tmp_path / "templates" / "ci" / "jenkins" / "day67-advanced-reference.Jenkinsfile").write_text(
        "pipeline {}\n", encoding="utf-8"
    )

    proc = _run_sdetkit(
        repo_root,
        tmp_path,
        "ci",
        "validate-templates",
        "--root",
        str(tmp_path),
        "--format",
        "json",
        "--strict",
    )
    assert proc.returncode == 2
    data = json.loads(proc.stdout)
    assert data.get("ok") is False
    missing = data.get("missing")
    assert isinstance(missing, list)
    assert any("templates/ci/tekton/day68-self-hosted-reference.yaml" in m for m in missing)


def test_ci_validate_templates_detects_missing_required_markers(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    (tmp_path / "templates" / "ci" / "gitlab").mkdir(parents=True)
    (tmp_path / "templates" / "ci" / "jenkins").mkdir(parents=True)
    (tmp_path / "templates" / "ci" / "tekton").mkdir(parents=True)

    (tmp_path / "templates" / "ci" / "gitlab" / "day66-advanced-reference.yml").write_text(
        "stages: [test]\n", encoding="utf-8"
    )
    (tmp_path / "templates" / "ci" / "jenkins" / "day67-advanced-reference.Jenkinsfile").write_text(
        "pipeline {}\n", encoding="utf-8"
    )
    (tmp_path / "templates" / "ci" / "tekton" / "day68-self-hosted-reference.yaml").write_text(
        "apiVersion: tekton.dev/v1\nkind: Pipeline\n", encoding="utf-8"
    )

    proc = _run_sdetkit(
        repo_root,
        tmp_path,
        "ci",
        "validate-templates",
        "--root",
        str(tmp_path),
        "--format",
        "json",
        "--strict",
    )
    assert proc.returncode == 2
    data = json.loads(proc.stdout)
    assert data.get("ok") is False
    checked = data.get("checked")
    assert isinstance(checked, list)
    failures = [x for x in checked if isinstance(x, dict) and x.get("ok") is False]
    assert failures
