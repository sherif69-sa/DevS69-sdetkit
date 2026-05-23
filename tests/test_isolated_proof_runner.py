from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from sdetkit.isolated_proof_runner import (
    PROOF_PROFILES,
    WORKSPACE_MUTATED_DURING_EXECUTION,
    main,
    render_markdown,
    run_isolated_proof,
)
from sdetkit.protected_verifier import verify_candidate


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    target = root / "src" / "sdetkit"
    target.mkdir(parents=True)
    (target / "example.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "pyproject.toml").write_text('[project]\nname = "example"\n', encoding="utf-8")
    return root


def _candidate_score() -> dict[str, Any]:
    return {
        "patch_id": "format-patch",
        "diagnosis_id": "formatting-autopilot",
        "score": 100,
        "changed_files": ["src/sdetkit/example.py"],
        "allowed_files": ["src/sdetkit/example.py"],
        "proof_requirements": ["python -m pre_commit run -a"],
        "decision": {
            "status": "candidate_for_protected_verification",
            "candidate_for_protected_verification": True,
            "automation_allowed": False,
        },
    }


def _setup_success_or_profile_success(
    args: list[str],
    **_kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, 0, stdout="proof ok\n", stderr="")


def test_isolated_runner_executes_allowlisted_profile_in_copied_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo(tmp_path)
    calls: list[tuple[list[str], Path, bool, int]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(
            (
                args,
                Path(kwargs["cwd"]),
                bool(kwargs["shell"]),
                int(kwargs["timeout"]),
            )
        )
        return _setup_success_or_profile_success(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)

    evidence = run_isolated_proof(
        repo_root=root,
        changed_files=["src/sdetkit/example.py"],
        profile_ids=["pre_commit_all"],
        timeout_seconds=20,
    )

    profile_call = calls[-1]
    assert profile_call[0][1:] == list(PROOF_PROFILES["pre_commit_all"].argv_suffix)
    assert profile_call[1] != root
    assert profile_call[2] is False
    assert profile_call[3] == 20

    assert evidence["status"] == "passed"
    assert evidence["changed_files"] == ["src/sdetkit/example.py"]
    assert evidence["changed_files_source"] == "caller_supplied_inventory_unverified"
    assert evidence["proof_results"][0]["command"] == "python -m pre_commit run -a"
    assert evidence["proof_results"][0]["status"] == "passed"
    assert evidence["isolation"]["source_workspace_used_as_command_cwd"] is False
    assert evidence["decision_boundary"]["automation_allowed"] is False
    assert evidence["decision_boundary"]["git_inventory_verified"] is False


def test_isolated_runner_output_is_consumable_by_protected_verifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo(tmp_path)
    monkeypatch.setattr(subprocess, "run", _setup_success_or_profile_success)

    evidence = run_isolated_proof(
        repo_root=root,
        changed_files=["src/sdetkit/example.py"],
        profile_ids=["pre_commit_all"],
    )
    result = verify_candidate(
        patch_score=_candidate_score(),
        verification_evidence=evidence,
    )

    assert result["decision"]["status"] == "structurally_verified_candidate"
    assert result["decision"]["structural_verification_passed"] is True
    assert result["decision"]["automation_allowed"] is False
    assert result["decision"]["merge_authorized"] is False
    assert result["decision"]["semantic_equivalence_proven"] is False


def test_isolated_runner_rejects_unknown_profiles_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo(tmp_path)

    def unexpected_run(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("subprocess must not execute for unknown profile")

    monkeypatch.setattr(subprocess, "run", unexpected_run)

    with pytest.raises(ValueError, match="unsupported proof profile"):
        run_isolated_proof(
            repo_root=root,
            changed_files=["src/sdetkit/example.py"],
            profile_ids=["command_from_evidence"],
        )


def test_isolated_runner_marks_timeout_as_failed_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo(tmp_path)

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[0] == "git":
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        raise subprocess.TimeoutExpired(args, kwargs["timeout"], output="partial output")

    monkeypatch.setattr(subprocess, "run", fake_run)

    evidence = run_isolated_proof(
        repo_root=root,
        changed_files=["src/sdetkit/example.py"],
        profile_ids=["pre_commit_all"],
        timeout_seconds=3,
    )

    proof = evidence["proof_results"][0]
    assert evidence["status"] == "failed"
    assert proof["status"] == "failed"
    assert proof["timed_out"] is True
    assert proof["exit_code"] == -1


def test_isolated_runner_fails_proof_when_command_mutates_copied_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo(tmp_path)

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[0] != "git":
            copied = Path(kwargs["cwd"]) / "src" / "sdetkit" / "example.py"
            copied.write_text("VALUE = 2\n", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    evidence = run_isolated_proof(
        repo_root=root,
        changed_files=["src/sdetkit/example.py"],
        profile_ids=["pre_commit_all"],
    )

    proof = evidence["proof_results"][0]
    assert evidence["status"] == "failed"
    assert proof[WORKSPACE_MUTATED_DURING_EXECUTION] is True
    assert proof["workspace_mutated_files"] == ["src/sdetkit/example.py"]
    assert (root / "src" / "sdetkit" / "example.py").read_text(encoding="utf-8") == "VALUE = 1\n"


def test_isolated_runner_markdown_renders_execution_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo(tmp_path)
    monkeypatch.setattr(subprocess, "run", _setup_success_or_profile_success)

    markdown = render_markdown(
        run_isolated_proof(
            repo_root=root,
            changed_files=["src/sdetkit/example.py"],
            profile_ids=["ruff_src_tests"],
        )
    )

    assert "# Isolated proof runner evidence" in markdown
    assert "Allowlisted profiles only: `true`" in markdown
    assert "Source workspace used as command cwd: `false`" in markdown
    assert "Network isolation enforced: `false`" in markdown
    assert "Git-derived file inventory verified: `false`" in markdown
    assert "Automation allowed: `false`" in markdown


def test_isolated_runner_cli_writes_evidence_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _repo(tmp_path)
    out_dir = tmp_path / "out"
    monkeypatch.setattr(subprocess, "run", _setup_success_or_profile_success)

    rc = main(
        [
            "--repo-root",
            str(root),
            "--changed-file",
            "src/sdetkit/example.py",
            "--profile",
            "mypy_src",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "verification-evidence.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "verification-evidence.md").read_text(encoding="utf-8")

    assert printed["status"] == "passed"
    assert saved["proof_results"][0]["command"] == "python -m mypy src"
    assert saved["decision_boundary"]["automation_allowed"] is False
    assert "# Isolated proof runner evidence" in markdown
