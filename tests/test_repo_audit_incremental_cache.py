from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run(tool_root: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tool_root / "src")
    env["PYTHONHASHSEED"] = "0"
    env["SOURCE_DATE_EPOCH"] = "1700000000"
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", "repo", *args],
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
    )


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, text=True, capture_output=True)


def _mk_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "toy_repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text("requests>=2\n", encoding="utf-8")
    (repo / "README.md").write_text("# toy\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "add", ".")
    subprocess.run(
        ["git", "-c", "user.name=toy", "-c", "user.email=toy@example.com", "commit", "-m", "init"],
        cwd=str(repo),
        check=True,
        text=True,
        capture_output=True,
    )
    return repo


def _json(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _normalize(payload: dict[str, Any], root: Path) -> dict[str, Any]:
    normalized = json.loads(json.dumps(payload))
    normalized["root"] = "<ROOT>"
    summary = normalized.get("summary")
    if isinstance(summary, dict):
        summary.pop("cache", None)
        summary.pop("incremental", None)
    for finding in normalized.get("findings", []):
        if isinstance(finding, dict) and isinstance(finding.get("path"), str):
            finding["path"] = str(finding["path"]).replace(str(root), "<ROOT>")
    return normalized


def test_incremental_run_cache_hit_invalidation_and_correctness(tmp_path: Path) -> None:
    tool_root = Path(__file__).resolve().parents[1]
    repo = _mk_repo(tmp_path)

    args = [
        "audit",
        ".",
        "--profile",
        "enterprise",
        "--format",
        "json",
        "--changed-only",
        "--cache-stats",
        "--fail-on",
        "none",
    ]

    first = _json(_run(tool_root, repo, *args))
    assert first["summary"]["cache"]["hit"] is False

    second = _json(_run(tool_root, repo, *args))
    assert second["summary"]["cache"]["hit"] is True
    assert _normalize(first, repo) == _normalize(second, repo)

    cache_root = repo / ".sdetkit" / "cache"
    assert cache_root.exists()
    run_cache_files = list((cache_root / "runs").glob("*.json"))
    assert run_cache_files
    run_doc = json.loads(run_cache_files[0].read_text(encoding="utf-8"))
    assert run_doc["schema_version"] == 1

    (repo / "requirements.txt").write_text("requests==2.0.0\n", encoding="utf-8")
    third = _json(_run(tool_root, repo, *args))
    assert third["summary"]["cache"]["hit"] is False

    full = _json(
        _run(
            tool_root,
            repo,
            "audit",
            ".",
            "--profile",
            "enterprise",
            "--format",
            "json",
            "--cache-stats",
            "--fail-on",
            "none",
        )
    )
    assert _normalize(full, repo) == _normalize(third, repo)


def test_incremental_run_cache_key_includes_changed_only_flags(tmp_path: Path) -> None:
    tool_root = Path(__file__).resolve().parents[1]
    repo = _mk_repo(tmp_path)

    base_args = [
        "audit",
        ".",
        "--profile",
        "enterprise",
        "--format",
        "json",
        "--changed-only",
        "--cache-stats",
        "--fail-on",
        "none",
    ]

    without_untracked = _json(_run(tool_root, repo, *base_args, "--no-include-untracked"))
    assert without_untracked["summary"]["cache"]["hit"] is False

    without_untracked_again = _json(_run(tool_root, repo, *base_args, "--no-include-untracked"))
    assert without_untracked_again["summary"]["cache"]["hit"] is True

    with_untracked = _json(_run(tool_root, repo, *base_args, "--include-untracked"))
    assert with_untracked["summary"]["cache"]["hit"] is False

    cache_root = repo / ".sdetkit" / "cache" / "runs"
    run_cache_files = sorted(cache_root.glob("*.json"))
    assert len(run_cache_files) == 2
