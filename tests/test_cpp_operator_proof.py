from __future__ import annotations

import json
from pathlib import Path

from sdetkit.cpp_operator_proof import (
    DOCTOR_JSON,
    DOCTOR_MD,
    PROOF_JSON,
    PROOF_MD,
    PROTECTED_VERIFIER_JSON,
    PROTECTED_VERIFIER_MD,
    REPO_MEMORY_JSON,
    SAFETY_GATE_JSON,
    SAFETY_GATE_MD,
    build_cpp_operator_proof,
    main,
)

FIXTURE_ROOT = Path("tests/fixtures/adoption_repos/cpp_operator_proof")
FAILURE_LOG = Path("tests/fixtures/ci_failures/cpp_ctest_operator_proof/ci_log.txt")


def _named(items: object) -> dict[str, dict[str, object]]:
    assert isinstance(items, list)
    return {
        str(item["name"]): item
        for item in items
        if isinstance(item, dict) and str(item.get("name", ""))
    }


def _commands(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    items = payload["recommended_proof_commands"]
    assert isinstance(items, list)
    return {
        str(item["command"]): item
        for item in items
        if isinstance(item, dict) and item.get("surface") == "cpp"
    }


def test_cpp_operator_proof_composes_shared_review_first_contracts(tmp_path: Path) -> None:
    out_dir = tmp_path / "cpp-proof"

    payload = build_cpp_operator_proof(
        repo=FIXTURE_ROOT,
        failure_log=FAILURE_LOG,
        out_dir=out_dir,
        check="ctest",
    )

    assert payload["schema_version"] == "sdetkit.ecosystem_operator_proof.v1"
    assert payload["ecosystem"] == "cpp"
    assert payload["status"] == "review_required"
    assert payload["repository_unchanged"] is True
    assert payload["verification"]["ok"] is True
    assert all(payload["verification"]["checks"].values())

    adoption = payload["adoption_surface"]
    languages = _named(adoption["detected_languages"])
    runners = _named(adoption["test_runners"])
    security = _named(adoption["security_tools"])
    artifacts = _named(adoption["artifact_surfaces"])
    commands = _commands(adoption)

    assert languages["cpp"]["confidence"] == "high"
    assert "ctest" in runners
    for tool in (
        "clang_tidy",
        "cppcheck",
        "address_sanitizer",
        "undefined_behavior_sanitizer",
        "codeql_cpp",
    ):
        assert tool in security
    assert "clang_format_evidence" in artifacts
    assert "cpp_compile_database_contract" in artifacts
    for command in (
        "cmake --preset ci",
        "cmake --build --preset ci",
        "ctest --preset ci",
        "clang-tidy -p build/ci src/calculator.cpp",
        "cppcheck --project=build/ci/compile_commands.json --enable=warning",
        "clang-format --dry-run --Werror src/calculator.cpp tests/calculator_test.cpp",
    ):
        assert command in commands
        assert commands[command]["auto_run_allowed"] is False
        assert commands[command]["executes_untrusted_code"] is True

    assert adoption["automation_allowed"] is False
    assert adoption["patch_application_allowed"] is False
    assert adoption["merge_authorized"] is False
    assert adoption["semantic_equivalence_proven"] is False

    vector = payload["failure_vector"]
    adapter = vector["adapter"]
    assert adapter == {
        "ecosystem": "cpp",
        "tool": "ctest_google_test",
        "confidence": "high",
        "uncertainty": [],
        "target_code_execution": False,
    }
    assert vector["failure_class"] == "test"
    assert vector["affected_files"] == ["tests/calculator_test.cpp"]
    assert vector["failing_test_or_check"] == "Calculator.Adds"
    assert vector["local_repro_command"] == "ctest --preset ci"
    assert vector["exit_code"] == 8
    assert vector["safe_fix_candidate"] is False
    assert vector["safe_fix_allowed"] is False

    safety = payload["safety_gate"]
    assert safety["review_first"] is True
    assert safety["safe_fix_allowed"] is False
    assert safety["reporting_only"] is True
    assert safety["automation_allowed"] is False
    assert safety["patch_application_allowed"] is False
    assert safety["security_dismissal_allowed"] is False
    assert safety["merge_authorized"] is False
    assert safety["semantic_equivalence_claim"] is False

    verifier = payload["protected_verifier"]
    decision = verifier["decision"]
    assert decision["status"] == "blocked_review_first"
    assert decision["review_first"] is True
    assert decision["candidate_for_protected_verification"] is False
    assert decision["protected_verification_passed"] is False
    assert decision["automation_allowed"] is False
    assert decision["patch_application_allowed"] is False
    assert decision["merge_authorized"] is False
    assert decision["semantic_equivalence_proven"] is False
    assert {item["code"] for item in verifier["risk_flags"] if item["blocking"] is True} == {
        "PATCH_SCORE_NOT_CANDIDATE",
        "PROOF_REQUIREMENTS_MISSING",
    }

    doctor = payload["doctor_report"]
    assert doctor["status"] == "review_required"
    assert doctor["confidence"] == "high"
    top_failure = doctor["failure_vector_evidence"]["top_failure"]
    assert top_failure["check"] == "ctest"
    assert top_failure["failure_type"] == "test"
    assert top_failure["local_repro_command"] == "ctest --preset ci"
    assert "failure_diagnosis" in doctor["roadmap_alignment"]["lanes"]
    assert doctor["safety_decision"]["automation_allowed"] is False
    assert doctor["safety_decision"]["patch_application_allowed"] is False
    assert doctor["safety_decision"]["security_dismissal_allowed"] is False
    assert doctor["safety_decision"]["merge_authorized"] is False
    assert doctor["safety_decision"]["semantic_equivalence_claim"] is False

    trajectory = payload["trajectory_evidence"]
    assert trajectory["record_count"] == 1
    assert trajectory["recurring_safe_fix_patterns"] == []
    assert trajectory["safety_gate_evidence"]["review_first_count"] == 1
    assert trajectory["failure_vector_contract_evidence"]["authority_boundary_preserved_count"] == 1

    repo_memory = payload["repo_memory_profile"]
    assert repo_memory["profile_status"] == "observation_only"
    assert repo_memory["memory_mode"] == "read_only_profile"
    assert repo_memory["command_profile"]["commands_executed_by_repo_memory"] is False
    contract = repo_memory["failure_vector_contract_evidence"]
    assert contract["record_count"] == 1
    assert contract["authority_boundary_preserved_count"] == 1
    assert set(contract["decision_boundary"].values()) == {False}

    boundary = payload["authority_boundary"]
    assert set(boundary.values()) == {False}

    for name in (
        PROOF_JSON,
        PROOF_MD,
        DOCTOR_JSON,
        DOCTOR_MD,
        SAFETY_GATE_JSON,
        SAFETY_GATE_MD,
        PROTECTED_VERIFIER_JSON,
        PROTECTED_VERIFIER_MD,
        REPO_MEMORY_JSON,
    ):
        assert (out_dir / name).exists(), name

    persisted = json.loads((out_dir / PROOF_JSON).read_text(encoding="utf-8"))
    markdown = (out_dir / PROOF_MD).read_text(encoding="utf-8")
    assert persisted["verification"]["ok"] is True
    assert "## What is detected" in markdown
    assert "## What is inferred" in markdown
    assert "## What is proven" in markdown
    assert "## Unsupported and manual" in markdown
    assert "target_code_execution=false" in markdown
    assert "automation_allowed=false" in markdown
    assert "patch_application_allowed=false" in markdown
    assert "security_dismissal_allowed=false" in markdown
    assert "merge_authorized=false" in markdown
    assert "semantic_equivalence_proven=false" in markdown


def test_cpp_operator_proof_unknown_saved_evidence_stays_low_confidence(
    tmp_path: Path,
) -> None:
    failure_log = tmp_path / "unknown.log"
    failure_log.write_text(
        "C++ build stopped without a structured compiler, linker, or test signal\n",
        encoding="utf-8",
    )

    payload = build_cpp_operator_proof(
        repo=FIXTURE_ROOT,
        failure_log=failure_log,
        out_dir=tmp_path / "unknown-proof",
        check="native-build",
    )

    vector = payload["failure_vector"]
    assert vector["adapter"]["tool"] == "unknown"
    assert vector["adapter"]["confidence"] == "low"
    assert vector["adapter"]["uncertainty"] == ["cpp_failure_not_classified"]
    assert vector["failure_class"] == "unknown"
    assert vector["local_repro_command"] is None
    assert payload["safety_gate"]["review_first"] is True
    assert payload["repository_unchanged"] is True
    assert payload["verification"]["ok"] is True


def test_cpp_operator_proof_cli_writes_deterministic_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = tmp_path / "cli-proof"

    rc = main(
        [
            "--repo",
            str(FIXTURE_ROOT),
            "--failure-log",
            str(FAILURE_LOG),
            "--out-dir",
            str(out_dir),
            "--check",
            "ctest",
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    persisted = json.loads((out_dir / PROOF_JSON).read_text(encoding="utf-8"))
    assert printed == {
        "schema_version": "sdetkit.ecosystem_operator_proof.v1",
        "ecosystem": "cpp",
        "status": "review_required",
        "verification_ok": True,
        "artifacts": [
            PROOF_JSON,
            PROOF_MD,
            DOCTOR_JSON,
            DOCTOR_MD,
            SAFETY_GATE_JSON,
            SAFETY_GATE_MD,
            PROTECTED_VERIFIER_JSON,
            PROTECTED_VERIFIER_MD,
            REPO_MEMORY_JSON,
        ],
        "authority_boundary": {
            "target_code_execution": False,
            "automation_allowed": False,
            "patch_application_allowed": False,
            "security_dismissal_allowed": False,
            "publication_authorized": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }
    assert persisted["verification"]["ok"] is True
    assert persisted["source_evidence"]["failure_log"] == FAILURE_LOG.name
    assert (out_dir / PROOF_MD).exists()
