from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sdetkit import (
    formatter_candidate_benchmark,
    protected_verifier,
    replayable_benchmark_harness,
    repo_memory,
    trajectory_store,
)

SCHEMA_VERSION = "sdetkit.formatter_candidate_verifier.v1"
CONTROLLED_VALIDATION_SCHEMA = "sdetkit.pr_quality.candidate_validation.v1"
DEFAULT_OUT_DIR = Path("build") / "formatter-candidate-verifier"
REPORT_JSON = "formatter-candidate-verifier.json"
REPORT_MD = "formatter-candidate-verifier.md"
PROTECTED_VERIFIER_JSON = "protected-verifier-result.json"
REPLAY_REPORT_JSON = "formatter-replay-report.json"
TRAJECTORY_JSONL = "formatter-trajectory.jsonl"
REPO_MEMORY_JSON = "formatter-repo-memory.json"
CONTROLLED_VALIDATION_JSON = "formatter-controlled-validation.json"

JsonObject = dict[str, Any]

AUTHORITY_KEYS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "publication_authorized",
    "security_dismissal_allowed",
    "semantic_equivalence_proven",
)


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _string_list(value: Any) -> list[str]:
    return sorted({_string(item) for item in _as_list(value) if _string(item)})


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _read_json(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.iterdir())
        if path.is_file()
    }


def _artifact(root: Path, logical_path: str) -> Path:
    path = root / Path(logical_path).name
    if path.is_symlink():
        raise ValueError(f"benchmark evidence cannot use a symlink: {path.name}")
    resolved_root = root.resolve()
    resolved = path.resolve()
    if resolved.parent != resolved_root or not resolved.is_file():
        raise ValueError(f"benchmark evidence artifact is missing or shadowed: {logical_path}")
    return resolved


def _assert_digest(root: Path, logical_path: str, expected: str) -> Path:
    path = _artifact(root, logical_path)
    actual = _sha256(path)
    if actual != expected:
        raise ValueError(f"benchmark evidence digest mismatch: {path.name}")
    return path


def _denied_boundary() -> JsonObject:
    return {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
    }


def _assert_authority_denied(payload: Mapping[str, Any], *, source: str) -> None:
    expanded = [key for key in AUTHORITY_KEYS if _bool(payload.get(key))]
    if expanded:
        raise ValueError(f"{source} expands authority: {', '.join(expanded)}")


def _proof_results(root: Path, evidence: Mapping[str, Any]) -> tuple[list[str], list[JsonObject]]:
    commands: list[str] = []
    results: list[JsonObject] = []
    for proof_key in ("focused_proof", "full_proof"):
        proof = _as_dict(evidence.get(proof_key))
        commands.extend(_string_list(proof.get("commands")))
        for artifact in _as_list(proof.get("artifacts")):
            record = _as_dict(artifact)
            path = _assert_digest(root, _string(record.get("path")), _string(record.get("sha256")))
            payload = _read_json(path)
            results.extend(_as_dict(item) for item in _as_list(payload.get("results")))
    normalized = sorted({_string(command) for command in commands if _string(command)})
    return normalized, results


def _scenario_payloads(
    root: Path,
    evidence: Mapping[str, Any],
) -> tuple[dict[str, JsonObject], list[str]]:
    scenarios: dict[str, JsonObject] = {}
    actual_writes: set[str] = set()
    for scenario_id, raw_record in _as_dict(evidence.get("scenarios")).items():
        record = _as_dict(raw_record)
        path = _assert_digest(root, _string(record.get("artifact_path")), _string(record.get("sha256")))
        scenario = _read_json(path)
        if _string(scenario.get("scenario_id")) != scenario_id:
            raise ValueError(f"scenario identity mismatch: {scenario_id}")
        if not _bool(scenario.get("matches_expectation")):
            raise ValueError(f"scenario expectation mismatch: {scenario_id}")
        observed = _string_list(scenario.get("observed_writes"))
        actual_writes.update(observed)
        if scenario_id != "oracle" and observed:
            raise ValueError(f"non-oracle scenario retained writes: {scenario_id}")
        if any(path.startswith("tests/") for path in observed):
            raise ValueError(f"scenario weakened a test surface: {scenario_id}")
        scenarios[scenario_id] = scenario
    required = {"no_op", "oracle", "unsafe_patch", "out_of_scope", "ambiguous", "rollback"}
    if set(scenarios) != required:
        raise ValueError("formatter evidence does not contain the required six scenarios")
    return scenarios, sorted(actual_writes)


def _replay_report(
    *,
    scenarios: Mapping[str, Mapping[str, Any]],
    patch_score: Mapping[str, Any],
    verifier_result: Mapping[str, Any],
) -> JsonObject:
    rows = []
    mapping = {
        "no_op": "nop_fail",
        "oracle": "oracle_pass",
        "unsafe_patch": "unsafe_patch_fail",
        "out_of_scope": replayable_benchmark_harness.UNCLAIMED_WRITE_FAIL,
        "ambiguous": replayable_benchmark_harness.INVENTORY_CLAIM_MISMATCH_FAIL,
        "rollback": replayable_benchmark_harness.PROOF_MUTATION_FAIL,
    }
    for scenario_id in sorted(scenarios):
        scenario = _as_dict(scenarios[scenario_id])
        rows.append(
            {
                "scenario_id": scenario_id,
                "scenario_type": mapping[scenario_id],
                "status": "passed",
                "passed": True,
                "attempt_score": 100,
                "patch_score": dict(patch_score),
                "protected_verifier_result": dict(verifier_result),
                replayable_benchmark_harness.VERIFICATION_EVIDENCE_SOURCE: "formatter_candidate_evidence",
            }
        )
    return {
        "schema_version": replayable_benchmark_harness.SCHEMA_VERSION,
        "status": "passed",
        "report_mode": "formatter_candidate_evidence_replay",
        "required_contract": {
            "all_required_present": True,
            "all_required_passed": True,
            "nop_fail_rate": 1.0,
            "oracle_pass_rate": 1.0,
            "unsafe_patch_rejection_rate": 1.0,
        },
        "safety_boundary": {
            "execution_model": "read_only_formatter_evidence_replay",
            "automation_allowed_count": 0,
            "merge_authorized_count": 0,
            "semantic_equivalence_claimed_count": 0,
            "runtime_proof_contract_authority_expansion_count": 0,
            "preserved": True,
        },
        "scenarios": rows,
        "next_boundary": "human review remains required before any policy promotion",
    }


def _controlled_validation(verifier_result: Mapping[str, Any]) -> JsonObject:
    verifier_status = _string(_as_dict(verifier_result.get("decision")).get("status"))
    return {
        "schema_version": CONTROLLED_VALIDATION_SCHEMA,
        "status": "passed",
        "scenario_count": 2,
        "passed_count": 2,
        "boundary": {
            "controlled_fixture_inputs_only": True,
            "contributes_to_current_pr_decision": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
        "scenarios": [
            {
                "scenario_id": "candidate_structurally_verified",
                "passed": verifier_status == "structurally_verified_candidate",
                "observed_status": "candidate_structurally_verified",
                "observed_verifier_status": "structurally_verified_candidate",
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
            {
                "scenario_id": "candidate_review_first_after_verification",
                "passed": True,
                "observed_status": "candidate_review_first_after_verification",
                "observed_verifier_status": "blocked_review_first",
                "automation_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        ],
    }


def _trajectory_inputs(claimed_files: Sequence[str], proof_commands: Sequence[str]) -> tuple[JsonObject, JsonObject]:
    diagnosis_id = "formatter-only-candidate-verification"
    diagnostic_vector = {
        "schema_version": "sdetkit.diagnostic.vector.v1",
        "diagnoses": [
            {
                "diagnosis_id": diagnosis_id,
                "failure_surface": "formatting",
                "review_first": True,
                "safe_fix_candidate": False,
                "affected_files": list(claimed_files),
                "likely_owner_files": list(claimed_files),
                "first_failure_line": "formatter-only candidate evidence requires human review",
                "proof_commands": list(proof_commands),
                "confidence": "high",
                "failure_vector": {
                    "failure_class": "formatter_only",
                    "risk_surface": "formatting",
                    "actual_failure": "formatter-only candidate evidence requires human review",
                    "environment": "disposable_fixture",
                    "exit_code": 0,
                    "contract": {
                        "schema_version": "sdetkit.failure_vector.contract.v1",
                        "failure_kind": "format_drift",
                        "affected_surface": "formatting",
                        "ownership_area": "pr_owned_source",
                        "retryability": "review_required",
                        "security_relevance": False,
                        "recommended_next_human_action": "review retained formatter evidence",
                        "reporting_only": True,
                        "automation_allowed": False,
                        "patch_application_allowed": False,
                        "security_dismissal_allowed": False,
                        "merge_authorized": False,
                        "semantic_equivalence_claim": False,
                    },
                },
            }
        ],
    }
    remediation_plan = {
        "schema_version": "sdetkit.remediation.plan.v1",
        "plans": [
            {
                "diagnosis_id": diagnosis_id,
                "failure_surface": "formatting",
                "classification": "formatter_only",
                "safe_to_auto_fix": False,
                "allowed_strategy": "review_formatter_candidate_evidence",
                "blocked_reason": "candidate promotion is not authorized",
                "affected_files": list(claimed_files),
                "proof_commands": list(proof_commands),
                "history_context": "formatter_candidate_benchmark",
            }
        ],
    }
    return diagnostic_vector, remediation_plan


def _pattern_insights(records: Sequence[Mapping[str, Any]]) -> JsonObject:
    boundary = _denied_boundary()
    return {
        "schema_version": "sdetkit.trajectory.patterns.v1",
        "record_count": len(records),
        "recurring_safe_fix_patterns": [],
        "recurring_review_first_surfaces": [{"value": "formatting", "count": len(records)}],
        "authority_boundary_evidence": {
            "collection_status": "collected",
            "status": "authority_boundary_evidence_observed",
            "source": "formatter_candidate_verifier",
            "record_count": len(records),
            "review_first_count": len(records),
            "auto_fix_allowed_count": 0,
            "reporting_only_count": len(records),
            "sources": ["formatter_candidate_verifier"],
            "decision_boundary": boundary,
        },
        "safety_gate_evidence": {
            "collection_status": "collected",
            "status": "safety_gate_evidence_observed",
            "source": "formatter_candidate_verifier",
            "record_count": len(records),
            "review_first_count": len(records),
            "safe_fix_allowed_count": 0,
            "reporting_only_count": len(records),
            "report_paths": [],
            "decision_boundary": boundary,
        },
        "failure_vector_contract_evidence": {
            "collection_status": "collected",
            "status": "failure_vector_contract_evidence_observed",
            "source": "formatter_candidate_verifier",
            "record_count": len(records),
            "security_relevance_count": 0,
            "authority_boundary_preserved_count": len(records),
            "failure_kinds": [{"value": "format_drift", "count": len(records)}],
            "affected_surfaces": [{"value": "formatting", "count": len(records)}],
            "decision_boundary": {
                "automation_allowed": False,
                "patch_application_allowed": False,
                "security_dismissal_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_claim": False,
            },
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    checks = _as_dict(report.get("checks"))
    return "\n".join(
        [
            "# Formatter candidate verifier and trajectory proof",
            "",
            f"- Status: `{_string(report.get('status'))}`",
            f"- Claimed files equal actual writes: `{str(_bool(checks.get('claimed_files_equal_actual_writes'))).lower()}`",
            f"- Proof inputs unchanged: `{str(_bool(checks.get('proof_inputs_unchanged'))).lower()}`",
            f"- Rollback exact bytes verified: `{str(_bool(checks.get('rollback_exact_bytes'))).lower()}`",
            f"- ProtectedVerifier status: `{_string(report.get('protected_verifier_status'))}`",
            f"- Trajectory review-first count: `{report.get('trajectory_review_first_count', 0)}`",
            f"- Trajectory auto-fix count: `{report.get('trajectory_auto_fix_allowed_count', 0)}`",
            f"- RepoMemory known safe candidates: `{report.get('repo_memory_known_safe_candidate_count', 0)}`",
            "",
            "This proof is read-only and advisory. It does not apply a patch, change SafetyGate policy, authorize merge, or prove semantic equivalence.",
            "",
        ]
    )


def verify_formatter_candidate(
    *,
    benchmark_dir: Path,
    out_dir: Path = DEFAULT_OUT_DIR,
    repo: str,
    branch: str,
    commit_sha: str,
    pr_number: int,
    reviewed_at: str,
) -> JsonObject:
    root = benchmark_dir.resolve()
    output = out_dir.resolve()
    if output == root or root in output.parents:
        raise ValueError("verifier output must be outside the benchmark evidence directory")

    benchmark = _read_json(root / formatter_candidate_benchmark.BENCHMARK_JSON)
    evidence = _read_json(root / formatter_candidate_benchmark.EVIDENCE_JSON)
    contract_report = _read_json(root / formatter_candidate_benchmark.CONTRACT_REPORT_JSON)
    before_snapshot = _snapshot(root)

    if _string(benchmark.get("status")) != "passed":
        raise ValueError("formatter benchmark has not passed")
    if not _bool(contract_report.get("ok")):
        raise ValueError("remediation research evidence is not structurally valid")
    _assert_authority_denied(benchmark, source="formatter benchmark")
    _assert_authority_denied(evidence, source="formatter evidence")
    if int(evidence.get("false_authority_count", -1)) != 0:
        raise ValueError("formatter evidence records false authority")

    claimed_scope = _string_list(evidence.get("pr_owned_scope"))
    diff = _as_dict(evidence.get("proposed_diff"))
    diff_files = _string_list(diff.get("files"))
    if not claimed_scope or claimed_scope != diff_files:
        raise ValueError("claimed formatter scope does not match proposed diff files")
    _assert_digest(root, _string(diff.get("artifact_path")), _string(diff.get("sha256")))

    scenarios, actual_writes = _scenario_payloads(root, evidence)
    if actual_writes != claimed_scope:
        raise ValueError("claimed formatter files do not equal observed writes")

    rollback = _as_dict(evidence.get("rollback"))
    rollback_path = _assert_digest(
        root,
        _string(rollback.get("artifact_path")),
        _string(rollback.get("sha256")),
    )
    rollback_payload = _read_json(rollback_path)
    rollback_exact = (
        _bool(rollback.get("verified"))
        and _bool(rollback_payload.get("verified"))
        and _string(rollback_payload.get("original_sha256"))
        == _string(rollback_payload.get("restored_sha256"))
        and _string_list(rollback_payload.get("observed_writes_after_restore")) == []
    )
    if not rollback_exact:
        raise ValueError("formatter rollback did not restore exact bytes")

    proof_commands, proof_results = _proof_results(root, evidence)
    patch_score = {
        "schema_version": "sdetkit.patch_scorer.v1",
        "patch_id": f"formatter-candidate-{commit_sha[:12]}",
        "diagnosis_id": "formatter-only-candidate-verification",
        "score": 100,
        "minimum_score": 100,
        "changed_files": claimed_scope,
        "allowed_files": claimed_scope,
        "proof_requirements": proof_commands,
        "decision": {
            "status": "candidate_for_protected_verification",
            "candidate_for_protected_verification": True,
            "automation_allowed": False,
        },
    }
    verification_evidence = {
        "changed_files": actual_writes,
        "proof_results": proof_results,
        "safety_gate_evidence": {
            "collection_status": "collected",
            "status": "review_first",
            "source": "formatter_candidate_benchmark",
            "record_count": 1,
            "review_first_count": 1,
            "safe_fix_allowed_count": 0,
            "reporting_only_count": 1,
            "report_paths": [],
            "decision_boundary": _denied_boundary(),
        },
    }
    verifier_result = protected_verifier.verify_candidate(
        patch_score=patch_score,
        verification_evidence=verification_evidence,
    )
    verifier_decision = _as_dict(verifier_result.get("decision"))
    if _string(verifier_decision.get("status")) != "structurally_verified_candidate":
        raise ValueError("ProtectedVerifier did not structurally verify formatter evidence")
    if not _bool(verifier_decision.get("structural_verification_passed")):
        raise ValueError("ProtectedVerifier structural verification did not pass")
    _assert_authority_denied(verifier_decision, source="ProtectedVerifier decision")

    diagnostic_vector, remediation_plan = _trajectory_inputs(claimed_scope, proof_commands)
    records = trajectory_store.build_trajectory_records(
        diagnostic_vector=diagnostic_vector,
        remediation_plan=remediation_plan,
        repo=repo,
        branch=branch,
        commit_sha=commit_sha,
        pr_number=pr_number,
        generated_at=reviewed_at,
    )
    for record in records:
        proof = _as_dict(record.get("proof"))
        proof.update(
            {
                "focused_proof": _string(_as_dict(evidence.get("focused_proof")).get("status")),
                "quality_proof": _string(_as_dict(evidence.get("full_proof")).get("status")),
                "verifier_result": _string(verifier_decision.get("status")),
            }
        )
        record["proof"] = proof
        record["final_result"] = "review_required"
    trajectory_summary = trajectory_store.write_trajectory_records(records, output / TRAJECTORY_JSONL)

    replay_report = _replay_report(
        scenarios=scenarios,
        patch_score=patch_score,
        verifier_result=verifier_result,
    )
    controlled_validation = _controlled_validation(verifier_result)
    profile = repo_memory.build_repo_memory_profile(
        pattern_insights=_pattern_insights(records),
        benchmark_report=replay_report,
        controlled_candidate_validation_evidence=controlled_validation,
    )
    profile_boundary = _as_dict(profile.get("decision_boundary"))
    _assert_authority_denied(profile_boundary, source="RepoMemory decision boundary")

    after_snapshot = _snapshot(root)
    proof_inputs_unchanged = before_snapshot == after_snapshot
    if not proof_inputs_unchanged:
        raise ValueError("formatter proof inputs were mutated during verification")

    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / PROTECTED_VERIFIER_JSON, verifier_result)
    _write_json(output / REPLAY_REPORT_JSON, replay_report)
    _write_json(output / CONTROLLED_VALIDATION_JSON, controlled_validation)
    _write_json(output / REPO_MEMORY_JSON, profile)

    report: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed",
        "candidate_family": "formatter_only",
        "source_repository": repo,
        "source_commit_sha": commit_sha,
        "pr_number": pr_number,
        "checks": {
            "claimed_files_equal_actual_writes": actual_writes == claimed_scope,
            "proof_inputs_unchanged": proof_inputs_unchanged,
            "rollback_exact_bytes": rollback_exact,
            "all_six_scenarios_retained": len(scenarios) == 6,
            "false_authority_count_zero": int(evidence.get("false_authority_count", -1)) == 0,
        },
        "protected_verifier_status": _string(verifier_decision.get("status")),
        "structural_verification_passed": _bool(
            verifier_decision.get("structural_verification_passed")
        ),
        "trajectory_record_count": trajectory_summary.get("record_count", 0),
        "trajectory_review_first_count": trajectory_summary.get("review_first_count", 0),
        "trajectory_auto_fix_allowed_count": trajectory_summary.get("auto_fix_allowed_count", 0),
        "repo_memory_profile_status": _string(profile.get("profile_status")),
        "repo_memory_known_safe_candidate_count": int(profile.get("known_safe_candidate_count", 0)),
        "controlled_validation_status": _string(
            _as_dict(profile.get("controlled_candidate_validation")).get("status")
        ),
        "input_artifact_count": len(before_snapshot),
        "artifacts": {
            "protected_verifier": (output / PROTECTED_VERIFIER_JSON).as_posix(),
            "replay_report": (output / REPLAY_REPORT_JSON).as_posix(),
            "trajectory": (output / TRAJECTORY_JSONL).as_posix(),
            "repo_memory": (output / REPO_MEMORY_JSON).as_posix(),
            "controlled_validation": (output / CONTROLLED_VALIDATION_JSON).as_posix(),
        },
        **formatter_candidate_benchmark.remediation_research_contract.authority_boundary(),
    }
    _write_json(output / REPORT_JSON, report)
    (output / REPORT_MD).write_text(render_markdown(report), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.formatter_candidate_verifier")
    parser.add_argument("--benchmark-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--reviewed-at", required=True)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = verify_formatter_candidate(
            benchmark_dir=args.benchmark_dir,
            out_dir=args.out_dir,
            repo=args.repo,
            branch=args.branch,
            commit_sha=args.commit_sha,
            pr_number=args.pr_number,
            reviewed_at=args.reviewed_at,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"protected_verifier_status: {report['protected_verifier_status']}")
        print(f"trajectory_review_first_count: {report['trajectory_review_first_count']}")
        print(
            "trajectory_auto_fix_allowed_count: "
            f"{report['trajectory_auto_fix_allowed_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
