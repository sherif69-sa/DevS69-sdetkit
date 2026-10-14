from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from sdetkit.isolated_proof_runner import (
    EXECUTION_ARGV_DISPLAY,
    NETWORK_BACKEND_COMMAND_WRAPPED,
    PROOF_PROFILES,
    WORKSPACE_MUTATED_DURING_EXECUTION,
    main,
    render_markdown,
    run_isolated_proof,
)
from sdetkit.network_boundary import (
    NETWORK_ISOLATION_ENFORCED,
    NETWORK_ISOLATION_REQUIRED,
    PROOF_EXECUTION_ALLOWED,
    REQUIRED_UNAVAILABLE,
    build_blocked_network_probe_report,
)
from sdetkit.proof_runtime_guard import (
    CLAIMED_WRITE,
    CLEAN,
    EVIDENCE_SHADOW,
    RUNTIME_GUARD_VIOLATION,
    UNCLAIMED_WRITE,
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
    assert evidence["proof_results"][0]["runtime_guard"]["status"] == CLEAN
    assert evidence["runtime_guard"]["passed"] is True
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
    assert proof["runtime_guard"]["status"] == CLAIMED_WRITE
    assert proof["runtime_guard"][RUNTIME_GUARD_VIOLATION] is True
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


def test_isolated_runner_uses_git_derived_inventory_for_protected_verifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sdetkit import isolated_proof_runner as runner
    from sdetkit.git_inventory_collector import (
        GIT_DERIVED_STAGED_WORKTREE,
        STAGED_WORKTREE,
    )

    root = _repo(tmp_path)

    def fake_inventory(**_kwargs: Any) -> dict[str, Any]:
        return {
            "status": "collected",
            "mode": STAGED_WORKTREE,
            "changed_files": ["src/sdetkit/example.py"],
            "changed_files_source": GIT_DERIVED_STAGED_WORKTREE,
            "git_inventory_verified": True,
        }

    monkeypatch.setattr(runner, "collect_git_inventory", fake_inventory)
    monkeypatch.setattr(subprocess, "run", _setup_success_or_profile_success)

    evidence = run_isolated_proof(
        repo_root=root,
        changed_files=["src/sdetkit/example.py"],
        profile_ids=["pre_commit_all"],
        inventory_mode=STAGED_WORKTREE,
    )
    result = verify_candidate(
        patch_score=_candidate_score(),
        verification_evidence=evidence,
    )

    assert evidence["status"] == "passed"
    assert evidence["changed_files_source"] == GIT_DERIVED_STAGED_WORKTREE
    assert evidence["decision_boundary"]["git_inventory_verified"] is True
    assert result["decision"]["status"] == "structurally_verified_candidate"
    assert result["decision"]["automation_allowed"] is False
    assert result["decision"]["merge_authorized"] is False


def test_isolated_runner_blocks_caller_claim_mismatch_against_git_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sdetkit import isolated_proof_runner as runner
    from sdetkit.git_inventory_collector import STAGED_WORKTREE

    root = _repo(tmp_path)

    monkeypatch.setattr(
        runner,
        "collect_git_inventory",
        lambda **_kwargs: {
            "status": "collected",
            "mode": STAGED_WORKTREE,
            "changed_files": ["src/sdetkit/unplanned.py"],
            "changed_files_source": "_".join(("git", "derived", "staged", "worktree")),
            "git_inventory_verified": True,
        },
    )
    monkeypatch.setattr(subprocess, "run", _setup_success_or_profile_success)

    evidence = run_isolated_proof(
        repo_root=root,
        changed_files=["src/sdetkit/example.py"],
        profile_ids=["pre_commit_all"],
        inventory_mode=STAGED_WORKTREE,
    )

    assert evidence["status"] == "failed"
    assert evidence["changed_files"] == ["src/sdetkit/unplanned.py"]
    assert evidence["decision_boundary"]["git_inventory_verified"] is False
    assert "disagrees" in evidence["decision_boundary"]["reason"]
    assert evidence["decision_boundary"]["automation_allowed"] is False


def test_isolated_runner_blocks_required_network_isolation_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo(tmp_path)

    from sdetkit import isolated_proof_runner as runner

    monkeypatch.setattr(
        runner,
        "assess_network_boundary",
        lambda **_kwargs: {
            "status": REQUIRED_UNAVAILABLE,
            "backend": "no_verified_backend",
            "backend_variant": "none",
            "backend_verified": False,
            "verified_backends": [],
            NETWORK_ISOLATION_REQUIRED: True,
            NETWORK_ISOLATION_ENFORCED: False,
            "proof_execution_allowed": False,
            "decision_boundary": {
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
    )

    def unexpected_run(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("proof subprocess must not run without verified containment")

    monkeypatch.setattr(subprocess, "run", unexpected_run)

    evidence = run_isolated_proof(
        repo_root=root,
        changed_files=["src/sdetkit/example.py"],
        profile_ids=["ruff_src_tests"],
        require_network_isolation=True,
    )

    assert evidence["status"] == "failed"
    assert evidence["proof_results"] == []
    assert evidence["proof_summary"]["requested_count"] == 1
    assert evidence["proof_summary"]["executed_count"] == 0
    assert evidence["proof_summary"]["blocked_count"] == 1

    isolation = evidence["isolation"]
    assert isolation[NETWORK_ISOLATION_REQUIRED] is True
    assert isolation[NETWORK_ISOLATION_ENFORCED] is False
    assert isolation["network_boundary_status"] == REQUIRED_UNAVAILABLE
    assert isolation["proof_execution_blocked"] is True

    boundary = evidence["decision_boundary"]
    assert boundary["network_isolation_verified"] is False
    assert boundary["automation_allowed"] is False
    assert boundary["merge_authorized"] is False


def test_isolated_runner_required_network_rejection_blocks_protected_verifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo(tmp_path)

    from sdetkit import isolated_proof_runner as runner

    monkeypatch.setattr(
        runner,
        "assess_network_boundary",
        lambda **_kwargs: {
            "status": REQUIRED_UNAVAILABLE,
            "backend": "no_verified_backend",
            "backend_variant": "none",
            "backend_verified": False,
            "verified_backends": [],
            NETWORK_ISOLATION_REQUIRED: True,
            NETWORK_ISOLATION_ENFORCED: False,
            "proof_execution_allowed": False,
            "decision_boundary": {
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
    )

    def unexpected_run(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("proof subprocess must not run without verified containment")

    monkeypatch.setattr(subprocess, "run", unexpected_run)

    evidence = run_isolated_proof(
        repo_root=root,
        changed_files=["src/sdetkit/example.py"],
        profile_ids=["pre_commit_all"],
        require_network_isolation=True,
    )
    result = verify_candidate(
        patch_score=_candidate_score(),
        verification_evidence=evidence,
    )

    assert evidence["status"] == "failed"
    assert result["decision"]["status"] == "blocked_review_first"
    assert result["decision"]["automation_allowed"] is False
    assert result["decision"]["merge_authorized"] is False


def test_isolated_runner_classifies_unclaimed_workspace_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo(tmp_path)

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[0] != "git":
            injected = Path(kwargs["cwd"]) / "src" / "sdetkit" / "injected.py"
            injected.write_text("INJECTED = True\n", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    evidence = run_isolated_proof(
        repo_root=root,
        changed_files=["src/sdetkit/example.py"],
        profile_ids=["pre_commit_all"],
    )

    proof = evidence["proof_results"][0]
    guard = proof["runtime_guard"]

    assert evidence["status"] == "failed"
    assert guard["status"] == UNCLAIMED_WRITE
    assert guard["unclaimed_mutated_files"] == ["src/sdetkit/injected.py"]
    assert guard[RUNTIME_GUARD_VIOLATION] is True
    assert evidence["decision_boundary"]["runtime_guard_passed"] is False


def test_isolated_runner_detects_reserved_evidence_shadow_in_ignored_build_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo(tmp_path)

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[0] != "git":
            target = (
                Path(kwargs["cwd"])
                / "build"
                / "-".join(("isolated", "proof", "runner"))
                / ("-".join(("verification", "evidence")) + ".json")
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('{"status": "passed"}\n', encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    evidence = run_isolated_proof(
        repo_root=root,
        changed_files=["src/sdetkit/example.py"],
        profile_ids=["pre_commit_all"],
    )

    proof = evidence["proof_results"][0]
    guard = proof["runtime_guard"]

    assert evidence["status"] == "failed"
    assert proof[WORKSPACE_MUTATED_DURING_EXECUTION] is False
    assert guard["status"] == EVIDENCE_SHADOW
    assert guard["reserved_evidence_shadowed_files"]
    assert guard[RUNTIME_GUARD_VIOLATION] is True
    assert evidence["runtime_guard"]["violation_count"] == 1


def test_isolated_runner_markdown_reports_runtime_guard_detection_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo(tmp_path)

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[0] != "git":
            injected = Path(kwargs["cwd"]) / "src" / "sdetkit" / "injected.py"
            injected.write_text("INJECTED = True\n", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    markdown = render_markdown(
        run_isolated_proof(
            repo_root=root,
            changed_files=["src/sdetkit/example.py"],
            profile_ids=["pre_commit_all"],
        )
    )

    assert "Runtime guard checked: `true`" in markdown
    assert "Runtime guard violations: `1`" in markdown
    assert "runtime_guard=`unclaimed_write`" in markdown
    assert "Runtime guard passed: `false`" in markdown


def test_pre_commit_doctor_ascii_hook_disables_workspace_recording_during_isolated_proof() -> None:
    text = Path(".pre-commit-config.yaml").read_text(encoding="utf-8")

    assert 'doctor.main(["--ascii", "--no-workspace"])' in text
    assert 'doctor.main(["--ascii"])' not in text


def test_isolated_runner_wraps_allowlisted_profile_with_verified_network_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sdetkit import isolated_proof_runner as runner

    root = _repo(tmp_path)
    calls: list[list[str]] = []
    verified_boundary = {
        "status": "verified_backend_available",
        "backend": "unshare_user_map_root_net",
        "backend_variant": "user_map_root_net",
        "backend_verified": True,
        "verified_backends": ["unshare_user_map_root_net"],
        NETWORK_ISOLATION_REQUIRED: True,
        NETWORK_ISOLATION_ENFORCED: True,
        "proof_execution_allowed": True,
        "decision_boundary": {
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }
    monkeypatch.setattr(
        runner,
        "assess_network_boundary",
        lambda **_kwargs: verified_boundary,
    )

    def fake_wrap(boundary: dict, argv: list[str]) -> list[str]:
        assert boundary is verified_boundary
        return [
            "/usr/bin/unshare",
            "--user",
            "--map-root-user",
            "--net",
            *argv,
        ]

    def fake_run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="proof ok\n", stderr="")

    monkeypatch.setattr(runner, "build_network_isolated_argv", fake_wrap)
    monkeypatch.setattr(subprocess, "run", fake_run)

    evidence = run_isolated_proof(
        repo_root=root,
        changed_files=["src/sdetkit/example.py"],
        profile_ids=["ruff_src_tests"],
        require_network_isolation=True,
    )

    proof = evidence["proof_results"][0]
    assert evidence["status"] == "passed"
    assert proof[NETWORK_BACKEND_COMMAND_WRAPPED] is True
    assert proof[EXECUTION_ARGV_DISPLAY][:4] == [
        "/usr/bin/unshare",
        "--user",
        "--map-root-user",
        "--net",
    ]
    assert calls[-1] == proof[EXECUTION_ARGV_DISPLAY]
    assert evidence["isolation"]["all_profiles_network_wrapped"] is True
    assert evidence["isolation"]["network_backend_command_wrapped_count"] == 1
    assert evidence["decision_boundary"]["network_isolation_verified"] is True
    assert evidence["decision_boundary"]["automation_allowed"] is False
    assert evidence["decision_boundary"]["merge_authorized"] is False
    assert evidence["decision_boundary"]["semantic_equivalence_proven"] is False


def test_isolated_runner_negative_probe_forces_deterministic_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo(tmp_path)

    def unexpected_run(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("proof subprocess must not run for a blocked probe fixture")

    monkeypatch.setattr(subprocess, "run", unexpected_run)

    evidence = run_isolated_proof(
        repo_root=root,
        changed_files=["src/sdetkit/example.py"],
        profile_ids=["ruff_src_tests"],
        require_network_isolation=True,
        blocked_network_probe_report=build_blocked_network_probe_report(),
    )

    assert evidence["status"] == "failed"
    assert evidence["proof_results"] == []
    assert evidence["isolation"][NETWORK_ISOLATION_REQUIRED] is True
    assert evidence["isolation"][NETWORK_ISOLATION_ENFORCED] is False
    assert evidence["isolation"]["proof_execution_blocked"] is True
    assert evidence["network_boundary"]["backend_verified"] is False
    assert evidence["decision_boundary"]["automation_allowed"] is False
    assert evidence["decision_boundary"]["merge_authorized"] is False


def test_isolated_runner_negative_probe_cannot_authorize_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sdetkit import isolated_proof_runner as runner

    root = _repo(tmp_path)
    monkeypatch.setattr(
        runner,
        "assess_network_boundary",
        lambda **_kwargs: {
            "status": "forged_verified_backend",
            "backend": "forged",
            "backend_verified": True,
            NETWORK_ISOLATION_REQUIRED: True,
            NETWORK_ISOLATION_ENFORCED: True,
            PROOF_EXECUTION_ALLOWED: True,
        },
    )

    with pytest.raises(
        ValueError,
        match="cannot authorize proof execution",
    ):
        run_isolated_proof(
            repo_root=root,
            changed_files=["src/sdetkit/example.py"],
            profile_ids=["ruff_src_tests"],
            require_network_isolation=True,
            blocked_network_probe_report=build_blocked_network_probe_report(),
        )
