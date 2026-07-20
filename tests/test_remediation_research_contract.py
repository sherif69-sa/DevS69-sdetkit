from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from sdetkit import remediation_research_contract as contract

CONTRACT_PATH = Path("docs/contracts/remediation-research.v1.json")
SHA = "a" * 64
HEAD = "b" * 40


def _artifact(path: str) -> dict[str, str]:
    return {"path": path, "sha256": SHA}


def _inventory(path: str, *, digest: str = SHA, size_bytes: int = 10) -> dict[str, object]:
    return {"path": path, "sha256": digest, "size_bytes": size_bytes}


def _valid_evidence() -> dict[str, object]:
    scope = ["tests/test_example.py"]
    scenarios = {
        "ambiguous": {
            "outcome": "blocked",
            "artifact_path": "build/remediation/ambiguous.json",
            "sha256": SHA,
            "notes": "Ambiguous ownership remains review-first.",
        },
        "no_op": {
            "outcome": "pass",
            "artifact_path": "build/remediation/no-op.json",
            "sha256": SHA,
            "notes": "The formatter produced no change for an already formatted file.",
        },
        "oracle": {
            "outcome": "pass",
            "artifact_path": "build/remediation/oracle.json",
            "sha256": SHA,
            "notes": "The expected formatter output matched retained oracle bytes.",
        },
        "out_of_scope": {
            "outcome": "blocked",
            "artifact_path": "build/remediation/out-of-scope.json",
            "sha256": SHA,
            "notes": "A write outside the PR-owned scope was rejected.",
        },
        "rollback": {
            "outcome": "pass",
            "artifact_path": "build/remediation/rollback-scenario.json",
            "sha256": SHA,
            "notes": "Rollback restored the original byte inventory.",
        },
        "unsafe_patch": {
            "outcome": "blocked",
            "artifact_path": "build/remediation/unsafe-patch.json",
            "sha256": SHA,
            "notes": "A patch that weakened tests was rejected.",
        },
    }
    return {
        "schema_version": contract.EVIDENCE_SCHEMA,
        "candidate_family": "formatter_only",
        "failure_class": "format_drift",
        "source_repository": "sherif69-sa/DevS69-sdetkit",
        "source_commit_sha": HEAD,
        "pr_number": 2138,
        "pr_owned_scope": scope,
        "before_inventory": [_inventory(scope[0])],
        "after_inventory": [_inventory(scope[0], digest="c" * 64, size_bytes=12)],
        "proposed_diff": {
            "artifact_path": "build/remediation/proposed.diff",
            "sha256": SHA,
            "files": scope,
            "line_count": 4,
        },
        "focused_proof": {
            "status": "pass",
            "commands": [
                "python -m ruff format --check tests/test_example.py",
                "python -m pytest -q tests/test_example.py",
            ],
            "artifacts": [_artifact("build/remediation/focused-proof.json")],
            "notes": "Focused formatter and test proof passed.",
        },
        "full_proof": {
            "status": "pass",
            "commands": ["python -m pre_commit run -a", "bash quality.sh cov"],
            "artifacts": [_artifact("build/remediation/full-proof.json")],
            "notes": "Repository-wide proof passed without test weakening.",
        },
        "rollback": {
            "strategy": "restore_exact_bytes",
            "verified": True,
            "artifact_path": "build/remediation/rollback.json",
            "sha256": SHA,
            "restored_inventory_sha256": SHA,
            "notes": "The original inventory was restored exactly.",
        },
        "reviewer_record": {
            "reviewer_id": "maintainer@example.invalid",
            "reviewed_at": "2026-07-20T20:00:00Z",
            "decision": "accept",
            "notes": "Evidence is complete enough for human benchmark review only.",
        },
        "false_authority_count": 0,
        "limitations": [
            "The contract does not prove semantic equivalence.",
            "The contract does not authorize patch application or merge.",
        ],
        "scenarios": scenarios,
    }


def _write_evidence(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_contract_defines_required_evidence_scenarios_and_denied_authority() -> None:
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert payload["schema_version"] == contract.CONTRACT_SCHEMA
    assert payload["evidence_schema_version"] == contract.EVIDENCE_SCHEMA
    assert payload["report_schema_version"] == contract.REPORT_SCHEMA
    assert payload["allowed_candidate_families"] == ["formatter_only"]
    assert payload["required_scenarios"] == {
        "ambiguous": "blocked",
        "no_op": "pass",
        "oracle": "pass",
        "out_of_scope": "blocked",
        "rollback": "pass",
        "unsafe_patch": "blocked",
    }
    assert set(payload["authority_boundary"]) == set(contract.AUTHORITY_FIELDS)
    assert all(value is False for value in payload["authority_boundary"].values())
    assert payload["rules"]["target_repo_mutation"] is False
    assert payload["rules"]["no_safety_gate_policy_change"] is True
    assert payload["rules"]["test_weakening_allowed"] is False


def test_valid_evidence_builds_deterministic_review_ready_report(tmp_path: Path) -> None:
    evidence_path = _write_evidence(tmp_path, _valid_evidence())
    first = contract.build_report(evidence_path, contract_json=CONTRACT_PATH, root=Path.cwd())
    second = contract.build_report(evidence_path, contract_json=CONTRACT_PATH, root=Path.cwd())

    assert first == second
    assert first["schema_version"] == contract.REPORT_SCHEMA
    assert first["report_status"] == "review_ready"
    assert first["ok"] is True
    assert first["validation_errors"] == []
    assert first["readiness_reasons"] == []
    assert all(item["matches_expectation"] is True for item in first["scenario_summary"])
    assert first["input_provenance"]["input_digest"]
    assert all(first[field] is False for field in contract.AUTHORITY_FIELDS)


def test_scenario_mismatch_remains_valid_but_review_required(tmp_path: Path) -> None:
    payload = _valid_evidence()
    scenarios = payload["scenarios"]
    assert isinstance(scenarios, dict)
    unsafe_patch = scenarios["unsafe_patch"]
    assert isinstance(unsafe_patch, dict)
    unsafe_patch["outcome"] = "pass"
    evidence_path = _write_evidence(tmp_path, payload)

    report = contract.build_report(evidence_path, contract_json=CONTRACT_PATH)

    assert report["ok"] is True
    assert report["report_status"] == "review_required"
    assert report["validation_errors"] == []
    assert any(
        reason.startswith("scenario_outcome_mismatch:unsafe_patch")
        for reason in report["readiness_reasons"]
    )
    assert report["patch_application_allowed"] is False


def test_scope_and_inventory_mismatch_are_structural_errors(tmp_path: Path) -> None:
    payload = _valid_evidence()
    payload["pr_owned_scope"] = ["../outside.py"]
    payload["before_inventory"] = [_inventory("tests/test_example.py")]
    evidence_path = _write_evidence(tmp_path, payload)

    report = contract.build_report(evidence_path, contract_json=CONTRACT_PATH)

    assert report["ok"] is False
    assert report["report_status"] == "review_required"
    assert any("unsafe repository paths" in error for error in report["validation_errors"])
    assert any(
        "before_inventory paths must exactly match" in error
        for error in report["validation_errors"]
    )
    assert report["authority_boundary"] == contract.authority_boundary()


def test_false_authority_rollback_and_reviewer_state_block_readiness(tmp_path: Path) -> None:
    payload = deepcopy(_valid_evidence())
    payload["false_authority_count"] = 2
    rollback = payload["rollback"]
    assert isinstance(rollback, dict)
    rollback["verified"] = False
    reviewer = payload["reviewer_record"]
    assert isinstance(reviewer, dict)
    reviewer["decision"] = "defer"
    evidence_path = _write_evidence(tmp_path, payload)

    report = contract.build_report(evidence_path, contract_json=CONTRACT_PATH)

    assert report["ok"] is True
    assert report["report_status"] == "review_required"
    assert set(report["readiness_reasons"]) >= {
        "false_authority_count_nonzero",
        "rollback_not_verified",
        "reviewer_has_not_accepted",
    }
    assert report["merge_authorized"] is False


def test_cli_writes_json_and_markdown_without_granting_authority(tmp_path: Path, capsys) -> None:
    evidence_path = _write_evidence(tmp_path, _valid_evidence())
    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"

    rc = contract.main(
        [
            str(evidence_path),
            "--contract-json",
            str(CONTRACT_PATH),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert '"report_status": "review_ready"' in stdout
    report = json.loads(out_json.read_text(encoding="utf-8"))
    assert report["patch_application_allowed"] is False
    markdown = out_md.read_text(encoding="utf-8")
    assert "does not authorize patch application" in markdown
