"""`sdetkit diagnose run`: saved CI log to an independently verified decision."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sdetkit import remediation_loop
from sdetkit.protected_proof_chain import verify_protected_proof_chain
from tests._cli_inprocess import run_cli

FORMAT_LOG = (
    "Run python -m ruff format --check src\n"
    "Would reformat: src/app.py\n"
    "1 file would be reformatted\n"
    "Process completed with exit code 1\n"
)
TEST_LOG = (
    "Run python -m pytest -q\n"
    "FAILED tests/test_app.py::test_value - AssertionError: assert 1 == 2\n"
    "Process completed with exit code 1\n"
)
PRE_COMMIT_CONFIG = """repos:
  - repo: local
    hooks:
      - id: ruff-format
        name: ruff format
        entry: python -m ruff format --check
        language: system
        types: [python]
"""


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # RepoMemory defaults to .sdetkit/memory under the working directory.
    monkeypatch.chdir(tmp_path)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _repo(tmp_path: Path, source: str = "x  =  1\n") -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text(source, encoding="utf-8")
    (repo / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG, encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    _git(repo, "remote", "add", "origin", "https://github.com/acme/widget.git")
    return repo


def _log(tmp_path: Path, text: str, check: str = "lint") -> Path:
    path = tmp_path / "logs" / check / "ci_log.txt"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_diagnose_only_stops_before_running_anything(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    out = tmp_path / "out"

    summary = remediation_loop.run_remediation_loop(
        log_paths=[_log(tmp_path, FORMAT_LOG)], repo_root=repo, out_dir=out
    )

    assert summary["decision"] == "proof_not_run"
    assert "--prove" in summary["next_action"]
    assert summary["candidate"]["allowed_files"] == ["src/app.py"]
    assert not (out / "proposed.patch").exists()
    assert (out / "trajectory.jsonl").is_file()
    assert summary["real_tree_modified"] is False
    assert all(value is False for value in summary["decision_boundary"].values())


def test_prove_fixes_in_a_copy_and_reaches_a_verified_candidate(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    out = tmp_path / "out"

    summary = remediation_loop.run_remediation_loop(
        log_paths=[_log(tmp_path, FORMAT_LOG)],
        repo_root=repo,
        out_dir=out,
        prove=True,
        timeout_seconds=120,
    )

    assert summary["decision"] == "verified_candidate", summary["reasons"]
    candidate = summary["candidate"]
    assert candidate["changed_files"] == ["src/app.py"]
    assert candidate["proof_status"] == "passed"
    assert candidate["verifier_status"] == "structurally_verified_candidate"
    assert "+x = 1" in (out / "proposed.patch").read_text(encoding="utf-8")
    # The caller's working tree is never touched.
    assert (repo / "src" / "app.py").read_text(encoding="utf-8") == "x  =  1\n"

    manifest = json.loads((out / "protected-proof-chain.json").read_text(encoding="utf-8"))
    artifacts = summary["artifacts"]
    verification = verify_protected_proof_chain(
        manifest,
        artifacts={
            "diagnostic_job": artifacts["job"],
            "failure_vector": artifacts["failure_vector"],
            "safety_gate": artifacts["safety_gate"],
            "proof_result": artifacts["verification_evidence"],
            "verifier_result": artifacts["verifier_result"],
            "patch_score": artifacts["patch_score"],
            "pr_report": artifacts["pr_report"],
            "trajectory": artifacts["trajectory"],
        },
        expected_repository="acme/widget",
        expected_commit_sha=summary["commit_sha"],
    )
    assert verification["ok"] is True, verification["mismatches"]


def test_test_failures_stay_review_first(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    summary = remediation_loop.run_remediation_loop(
        log_paths=[_log(tmp_path, TEST_LOG, check="tests")],
        repo_root=repo,
        out_dir=tmp_path / "out",
        prove=True,
    )

    assert summary["decision"] == "review_first"
    assert summary["candidate"] == {}
    assert summary["reasons"]
    assert not (tmp_path / "out" / "proposed.patch").exists()


def test_stale_log_on_an_already_fixed_tree_reports_no_change(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source="x = 1\n")

    summary = remediation_loop.run_remediation_loop(
        log_paths=[_log(tmp_path, FORMAT_LOG)],
        repo_root=repo,
        out_dir=tmp_path / "out",
        prove=True,
        timeout_seconds=120,
    )

    assert summary["decision"] == "no_change"
    assert "stale or already fixed" in summary["next_action"]


def test_trajectory_history_accumulates_across_runs(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    out = tmp_path / "out"
    log = _log(tmp_path, FORMAT_LOG)

    remediation_loop.run_remediation_loop(log_paths=[log], repo_root=repo, out_dir=out)
    remediation_loop.run_remediation_loop(log_paths=[log], repo_root=repo, out_dir=out)

    lines = (out / "trajectory.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_cli_runs_the_loop_through_the_diagnose_group(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    out = tmp_path / "out"

    result = run_cli(
        "diagnose",
        "run",
        "--log",
        str(_log(tmp_path, FORMAT_LOG)),
        "--repo-root",
        str(repo),
        "--out-dir",
        str(out),
        "--format",
        "json",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "sdetkit.remediation_loop.v1"
    assert payload["decision"] == "proof_not_run"


def test_cli_reports_a_missing_log_as_a_usage_error(tmp_path: Path) -> None:
    result = run_cli(
        "diagnose", "run", "--log", str(tmp_path / "missing.txt"), "--out-dir", str(tmp_path)
    )

    assert result.returncode == 2
    assert "diagnose run error" in result.stderr
