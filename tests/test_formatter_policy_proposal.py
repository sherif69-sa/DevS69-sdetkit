from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from sdetkit import formatter_candidate_benchmark as benchmark
from sdetkit import formatter_candidate_verifier as verifier
from sdetkit import formatter_policy_proposal as proposal

RESEARCH_CONTRACT = Path("docs/contracts/remediation-research.v1.json")
POLICY_CONTRACT = Path("docs/contracts/formatter-policy-proposal.v1.json")
HEAD = "c" * 40
REPO = "sherif69-sa/DevS69-sdetkit"
PR_NUMBER = 2141


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _build_verifier_packet(tmp_path: Path) -> Path:
    benchmark_dir = tmp_path / "benchmark"
    benchmark_report = benchmark.run_formatter_candidate_benchmark(
        source_repository=REPO,
        source_commit_sha=HEAD,
        pr_number=PR_NUMBER,
        reviewer_id="maintainer@example.invalid",
        reviewed_at="2026-07-21T02:00:00Z",
        reviewer_decision="accept",
        reviewer_notes="Accepted formatter evidence for policy proposal review.",
        out_dir=benchmark_dir,
        contract_json=RESEARCH_CONTRACT,
        command_runner=_fake_runner,
    )
    assert benchmark_report["status"] == "passed"

    verifier_dir = tmp_path / "verifier"
    verifier_report = verifier.verify_formatter_candidate(
        benchmark_dir=benchmark_dir,
        out_dir=verifier_dir,
        repo=REPO,
        branch="feature/formatter-policy-proposal",
        commit_sha=HEAD,
        pr_number=PR_NUMBER,
        reviewed_at="2026-07-21T02:00:00Z",
    )
    assert verifier_report["status"] == "passed"
    return verifier_dir


def _approval_record(tmp_path: Path, verifier_dir: Path) -> Path:
    report_path = verifier_dir / verifier.REPORT_JSON
    approval = {
        "schema_version": proposal.APPROVAL_SCHEMA_VERSION,
        "provider": "github",
        "provider_identity_verified": True,
        "reviewer_id": "sherif69-sa",
        "approved_at": "2026-07-21T02:15:00Z",
        "decision": "approve_proposal",
        "source_repository": REPO,
        "source_commit_sha": HEAD,
        "source_pr_number": PR_NUMBER,
        "approval_reference": f"https://github.com/{REPO}/pull/{PR_NUMBER}",
        "verifier_report_sha256": _sha256(report_path),
        "limitations_acknowledged": True,
    }
    path = tmp_path / "formatter-policy-approval.json"
    path.write_text(json.dumps(approval, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _build_proposal(tmp_path: Path, verifier_dir: Path, approval_path: Path) -> dict[str, Any]:
    return proposal.build_formatter_policy_proposal(
        verifier_dir=verifier_dir,
        approval_record_json=approval_path,
        out_dir=tmp_path / "proposal",
        contract_json=POLICY_CONTRACT,
    )


def test_formatter_policy_proposal_promotes_only_human_reviewable_proposal(
    tmp_path: Path,
) -> None:
    verifier_dir = _build_verifier_packet(tmp_path)
    approval_path = _approval_record(tmp_path, verifier_dir)

    report = _build_proposal(tmp_path, verifier_dir, approval_path)

    assert report["schema_version"] == proposal.SCHEMA_VERSION
    assert report["status"] == "passed"
    assert report["proposal_status"] == "eligible_for_human_policy_proposal"
    assert report["candidate_family"] == "formatter_only"
    assert report["promotion_mode"] == "proposal_only"
    assert report["proposal_eligible"] is True
    assert report["execution_eligible"] is False
    assert report["branch_execution_allowed"] is False
    assert report["safe_fix_allowed"] is False
    assert report["review_required"] is True
    assert report["safety_gate_policy_changed"] is False
    assert report["checks"] == {
        "candidate_is_formatter_only": True,
        "verifier_report_passed": True,
        "all_verifier_checks_passed": True,
        "protected_verifier_structural_only": True,
        "all_trajectories_review_first": True,
        "repo_memory_authority_zero": True,
        "provider_identity_verified": True,
        "approval_bound_to_exact_evidence": True,
        "verifier_inputs_unchanged": True,
    }
    assert report["automation_allowed"] is False
    assert report["patch_application_allowed"] is False
    assert report["merge_authorized"] is False
    assert report["publication_authorized"] is False
    assert report["security_dismissal_allowed"] is False
    assert report["semantic_equivalence_proven"] is False


def test_formatter_policy_proposal_writes_auditable_outputs(tmp_path: Path) -> None:
    verifier_dir = _build_verifier_packet(tmp_path)
    approval_path = _approval_record(tmp_path, verifier_dir)

    report = _build_proposal(tmp_path, verifier_dir, approval_path)
    out_dir = tmp_path / "proposal"

    stored = json.loads((out_dir / proposal.REPORT_JSON).read_text(encoding="utf-8"))
    assert stored == report
    markdown = (out_dir / proposal.REPORT_MD).read_text(encoding="utf-8")
    assert "eligible_for_human_policy_proposal" in markdown
    assert "Branch execution allowed: `false`" in markdown
    assert report["approval_binding"]["identity_authentication"] == (
        "asserted_by_hosting_provider_not_reverified_locally"
    )


def test_formatter_policy_proposal_preserves_verifier_inputs(tmp_path: Path) -> None:
    verifier_dir = _build_verifier_packet(tmp_path)
    approval_path = _approval_record(tmp_path, verifier_dir)
    before = {path.name: path.read_bytes() for path in verifier_dir.iterdir() if path.is_file()}

    _build_proposal(tmp_path, verifier_dir, approval_path)

    after = {path.name: path.read_bytes() for path in verifier_dir.iterdir() if path.is_file()}
    assert after == before


def test_formatter_policy_proposal_rejects_unverified_provider_identity(tmp_path: Path) -> None:
    verifier_dir = _build_verifier_packet(tmp_path)
    approval_path = _approval_record(tmp_path, verifier_dir)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["provider_identity_verified"] = False
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    with pytest.raises(ValueError, match="identity must be verified"):
        _build_proposal(tmp_path, verifier_dir, approval_path)


def test_formatter_policy_proposal_rejects_stale_verifier_digest(tmp_path: Path) -> None:
    verifier_dir = _build_verifier_packet(tmp_path)
    approval_path = _approval_record(tmp_path, verifier_dir)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["verifier_report_sha256"] = "0" * 64
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    with pytest.raises(ValueError, match="verifier_report_sha256"):
        _build_proposal(tmp_path, verifier_dir, approval_path)


def test_formatter_policy_proposal_rejects_authority_expansion(tmp_path: Path) -> None:
    verifier_dir = _build_verifier_packet(tmp_path)
    report_path = verifier_dir / verifier.REPORT_JSON
    verifier_report = json.loads(report_path.read_text(encoding="utf-8"))
    verifier_report["patch_application_allowed"] = True
    report_path.write_text(json.dumps(verifier_report), encoding="utf-8")
    approval_path = _approval_record(tmp_path, verifier_dir)

    with pytest.raises(ValueError, match="expands authority"):
        _build_proposal(tmp_path, verifier_dir, approval_path)


def test_formatter_policy_proposal_rejects_trajectory_auto_fix(tmp_path: Path) -> None:
    verifier_dir = _build_verifier_packet(tmp_path)
    approval_path = _approval_record(tmp_path, verifier_dir)
    trajectory_path = verifier_dir / verifier.TRAJECTORY_JSONL
    record = json.loads(trajectory_path.read_text(encoding="utf-8"))
    record["decision"]["auto_fix_allowed"] = True
    trajectory_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="review-first without auto-fix"):
        _build_proposal(tmp_path, verifier_dir, approval_path)


def test_formatter_policy_proposal_rejects_non_formatter_family(tmp_path: Path) -> None:
    verifier_dir = _build_verifier_packet(tmp_path)
    report_path = verifier_dir / verifier.REPORT_JSON
    verifier_report = json.loads(report_path.read_text(encoding="utf-8"))
    verifier_report["candidate_family"] = "lint"
    report_path.write_text(json.dumps(verifier_report), encoding="utf-8")
    approval_path = _approval_record(tmp_path, verifier_dir)

    with pytest.raises(ValueError, match="only formatter_only"):
        _build_proposal(tmp_path, verifier_dir, approval_path)


def test_formatter_policy_proposal_cli_emits_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verifier_dir = _build_verifier_packet(tmp_path)
    approval_path = _approval_record(tmp_path, verifier_dir)
    out_dir = tmp_path / "cli-proposal"

    rc = proposal.main(
        [
            "--verifier-dir",
            str(verifier_dir),
            "--approval-record",
            str(approval_path),
            "--out-dir",
            str(out_dir),
            "--contract-json",
            str(POLICY_CONTRACT),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["proposal_eligible"] is True
    assert printed["branch_execution_allowed"] is False
    assert (out_dir / proposal.REPORT_JSON).exists()
    assert (out_dir / proposal.REPORT_MD).exists()
