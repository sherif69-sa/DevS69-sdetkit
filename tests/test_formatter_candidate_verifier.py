from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import pytest

from sdetkit import formatter_candidate_benchmark as benchmark
from sdetkit import formatter_candidate_verifier as verifier

CONTRACT_PATH = Path("docs/contracts/remediation-research.v1.json")
HEAD = "b" * 40


def _fake_runner(argv: Sequence[str], cwd: Path) -> dict[str, Any]:
    command = " ".join(str(item) for item in argv)
    target = cwd / benchmark.TARGET_PATH
    is_format = "format" in argv
    is_check = "--check" in argv
    if is_format and not is_check and argv[-1] == benchmark.TARGET_PATH:
        if target.read_bytes() == benchmark.UNFORMATTED_SOURCE:
            target.write_bytes(benchmark.FORMATTED_SOURCE)
    if is_format and is_check:
        status = "pass" if target.read_bytes() == benchmark.FORMATTED_SOURCE else "fail"
    else:
        status = "pass"
    return {
        "command": command,
        "status": status,
        "exit_code": 0 if status == "pass" else 1,
        "stdout": "",
        "stderr": "",
    }


def _build_packet(tmp_path: Path) -> Path:
    out_dir = tmp_path / "benchmark"
    report = benchmark.run_formatter_candidate_benchmark(
        source_repository="sherif69-sa/DevS69-sdetkit",
        source_commit_sha=HEAD,
        pr_number=2141,
        reviewer_id="maintainer@example.invalid",
        reviewed_at="2026-07-21T01:00:00Z",
        reviewer_decision="accept",
        reviewer_notes="Accepted fixture evidence for verifier contract proof.",
        out_dir=out_dir,
        contract_json=CONTRACT_PATH,
        command_runner=_fake_runner,
    )
    assert report["status"] == "passed"
    return out_dir


def _verify(tmp_path: Path, benchmark_dir: Path) -> dict[str, Any]:
    return verifier.verify_formatter_candidate(
        benchmark_dir=benchmark_dir,
        out_dir=tmp_path / "verifier",
        repo="sherif69-sa/DevS69-sdetkit",
        branch="feature/formatter-verifier-trajectory-proof",
        commit_sha=HEAD,
        pr_number=2141,
        reviewed_at="2026-07-21T01:00:00Z",
    )


def test_formatter_candidate_verifier_proves_scope_trajectory_and_memory(tmp_path: Path) -> None:
    benchmark_dir = _build_packet(tmp_path)
    report = _verify(tmp_path, benchmark_dir)

    assert report["schema_version"] == verifier.SCHEMA_VERSION
    assert report["status"] == "passed"
    assert report["candidate_family"] == "formatter_only"
    assert report["checks"] == {
        "all_six_scenarios_retained": True,
        "claimed_files_equal_actual_writes": True,
        "false_authority_count_zero": True,
        "proof_inputs_unchanged": True,
        "rollback_exact_bytes": True,
    }
    assert report["protected_verifier_status"] == "structurally_verified_candidate"
    assert report["structural_verification_passed"] is True
    assert report["trajectory_record_count"] == 1
    assert report["trajectory_review_first_count"] == 1
    assert report["trajectory_auto_fix_allowed_count"] == 0
    assert report["repo_memory_profile_status"] == "benchmark_supported_memory"
    assert report["repo_memory_known_safe_candidate_count"] == 0
    assert report["controlled_validation_status"] == "controlled_validation_passed"
    assert report["automation_allowed"] is False
    assert report["patch_application_allowed"] is False
    assert report["merge_authorized"] is False
    assert report["publication_authorized"] is False
    assert report["security_dismissal_allowed"] is False
    assert report["semantic_equivalence_proven"] is False


def test_formatter_candidate_verifier_writes_review_first_trajectory_and_memory(
    tmp_path: Path,
) -> None:
    benchmark_dir = _build_packet(tmp_path)
    _verify(tmp_path, benchmark_dir)
    out_dir = tmp_path / "verifier"

    lines = (out_dir / verifier.TRAJECTORY_JSONL).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    trajectory = json.loads(lines[0])
    assert trajectory["decision"]["review_first"] is True
    assert trajectory["decision"]["auto_fix_allowed"] is False
    assert trajectory["proof"]["focused_proof"] == "pass"
    assert trajectory["proof"]["quality_proof"] == "pass"
    assert trajectory["proof"]["verifier_result"] == "structurally_verified_candidate"
    assert trajectory["final_result"] == "review_required"
    assert trajectory["authority_boundary"]["automation_allowed"] is False
    assert trajectory["authority_boundary"]["patch_application_allowed"] is False
    assert trajectory["authority_boundary"]["merge_authorized"] is False

    memory = json.loads((out_dir / verifier.REPO_MEMORY_JSON).read_text(encoding="utf-8"))
    assert memory["profile_status"] == "benchmark_supported_memory"
    assert memory["known_safe_candidate_count"] == 0
    assert memory["decision_boundary"]["automation_allowed"] is False
    assert memory["decision_boundary"]["merge_authorized"] is False
    assert memory["decision_boundary"]["semantic_equivalence_proven"] is False
    assert memory["controlled_candidate_validation"]["status"] == "controlled_validation_passed"
    assert memory["controlled_candidate_validation"]["current_pr_decision_input"] is False


def test_formatter_candidate_verifier_preserves_all_input_artifacts(tmp_path: Path) -> None:
    benchmark_dir = _build_packet(tmp_path)
    before = {path.name: path.read_bytes() for path in benchmark_dir.iterdir() if path.is_file()}

    report = _verify(tmp_path, benchmark_dir)

    after = {path.name: path.read_bytes() for path in benchmark_dir.iterdir() if path.is_file()}
    assert report["checks"]["proof_inputs_unchanged"] is True
    assert after == before


def test_formatter_candidate_verifier_rejects_tampered_scenario_digest(tmp_path: Path) -> None:
    benchmark_dir = _build_packet(tmp_path)
    scenario = benchmark_dir / "scenario-oracle.json"
    scenario.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="digest mismatch"):
        _verify(tmp_path, benchmark_dir)


def test_formatter_candidate_verifier_rejects_claimed_scope_mismatch(tmp_path: Path) -> None:
    benchmark_dir = _build_packet(tmp_path)
    evidence_path = benchmark_dir / benchmark.EVIDENCE_JSON
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["pr_owned_scope"] = [benchmark.TARGET_PATH, "src/other.py"]
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="claimed formatter scope"):
        _verify(tmp_path, benchmark_dir)


def test_formatter_candidate_verifier_rejects_false_authority(tmp_path: Path) -> None:
    benchmark_dir = _build_packet(tmp_path)
    benchmark_path = benchmark_dir / benchmark.BENCHMARK_JSON
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    payload["automation_allowed"] = True
    benchmark_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="expands authority"):
        _verify(tmp_path, benchmark_dir)


def test_formatter_candidate_verifier_cli_writes_read_only_outputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    benchmark_dir = _build_packet(tmp_path)
    out_dir = tmp_path / "cli-verifier"
    rc = verifier.main(
        [
            "--benchmark-dir",
            str(benchmark_dir),
            "--out-dir",
            str(out_dir),
            "--repo",
            "sherif69-sa/DevS69-sdetkit",
            "--branch",
            "feature/formatter-verifier-trajectory-proof",
            "--commit-sha",
            HEAD,
            "--pr-number",
            "2141",
            "--reviewed-at",
            "2026-07-21T01:00:00Z",
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "passed"
    assert printed["protected_verifier_status"] == "structurally_verified_candidate"
    assert printed["trajectory_auto_fix_allowed_count"] == 0
    assert (out_dir / verifier.REPORT_JSON).exists()
    assert (out_dir / verifier.REPORT_MD).exists()
    assert (out_dir / verifier.PROTECTED_VERIFIER_JSON).exists()
    assert (out_dir / verifier.TRAJECTORY_JSONL).exists()
    assert (out_dir / verifier.REPO_MEMORY_JSON).exists()
