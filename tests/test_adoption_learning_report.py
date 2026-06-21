from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_learning_report import (
    ACCEPTED_MATRIX_SCHEMA,
    ACCEPTED_REPO_MEMORY_SCHEMAS,
    SCHEMA_VERSION,
    adoption_learning_input_provenance,
    build_adoption_learning_report,
    check_adoption_learning_report_freshness,
    validate_adoption_learning_report_freshness,
    write_adoption_learning_report_artifacts,
)


def _matrix(path: Path) -> Path:
    payload = {
        "schema_version": "sdetkit.adoption_real_world_learning_matrix.v1",
        "matrix_status": "passed",
        "repo_count": 10,
        "upgrade_candidates": [
            {
                "upgrade_candidate_title": (
                    "feat(adoption): improve artifact path detection from real-world matrix evidence"
                ),
                "classification": "artifact_path_gap",
                "frequency_across_matrix": 2,
                "observed_in_repos": ["repo-a", "repo-b"],
                "owner_files": ["src/sdetkit/adoption_repo_topology.py"],
                "proof_needed": [
                    "python -m pytest -q tests/test_adoption_repo_topology.py -o addopts="
                ],
                "reason_from_real_repo": "artifact_path_gap appeared in 2 repo(s).",
                "review_first": True,
                "safe_to_patch": False,
            },
            {
                "upgrade_candidate_title": (
                    "feat(adoption): strengthen proof-command mapping from real-world matrix evidence"
                ),
                "classification": "weak_proof_command_mapping",
                "frequency_across_matrix": 4,
                "observed_in_repos": ["repo-c", "repo-d", "repo-e", "repo-f"],
                "owner_files": ["src/sdetkit/adoption_proof_recommendations.py"],
                "proof_needed": [
                    "python -m pytest -q tests/test_adoption_proof_recommendations.py -o addopts="
                ],
                "reason_from_real_repo": "weak_proof_command_mapping appeared in 4 repo(s).",
                "review_first": True,
                "safe_to_patch": False,
            },
            {
                "upgrade_candidate_title": (
                    "feat(adoption): improve CI provider detection from real-world matrix evidence"
                ),
                "classification": "unsupported_ci_provider",
                "frequency_across_matrix": 1,
                "observed_in_repos": ["repo-g"],
                "owner_files": ["src/sdetkit/adoption_surface.py"],
                "proof_needed": ["python -m pytest -q tests/test_adoption_surface.py -o addopts="],
                "reason_from_real_repo": "unsupported_ci_provider appeared in 1 repo.",
                "review_first": True,
                "safe_to_patch": False,
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_adoption_learning_report_prioritizes_matrix_candidates(tmp_path: Path) -> None:
    matrix_json = _matrix(tmp_path / "matrix.json")

    payload = build_adoption_learning_report(matrix_json)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["source_matrix_status"] == "passed"
    assert payload["source_repo_count"] == 10
    assert payload["candidate_count"] == 3
    provenance = payload["input_provenance"]
    assert provenance["digest_algorithm"] == "sha256"
    assert len(provenance["input_digest"]) == 64
    assert provenance["matrix_schema_version"] == ACCEPTED_MATRIX_SCHEMA
    assert provenance["current_head_available"] is True
    relationships = payload["source_relationships"]
    assert relationships["matrix_schema_accepted"] is True
    assert relationships["repo_memory_profile_schema_accepted"] is True
    assert relationships["current_head_bound"] is True
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert payload["rules"]["source_matrix_only"] is True
    assert payload["rules"]["target_repos_read"] is False
    assert payload["rules"]["install_dependencies"] is False
    assert payload["rules"]["target_tests_executed"] is False
    assert payload["rules"]["target_repo_mutation"] is False

    top = payload["top_candidate"]
    assert top["classification"] == "weak_proof_command_mapping"
    assert top["priority"] == "P1"
    assert top["rank"] == 1
    assert top["safe_to_patch"] is False
    assert top["review_first"] is True

    candidates = payload["prioritized_upgrade_candidates"]
    assert [candidate["rank"] for candidate in candidates] == [1, 2, 3]
    assert all(candidate["safe_to_patch"] is False for candidate in candidates)
    assert all(candidate["review_first"] is True for candidate in candidates)


def test_adoption_learning_report_writes_json_and_markdown(tmp_path: Path) -> None:
    matrix_json = _matrix(tmp_path / "matrix.json")
    out = tmp_path / "reports" / "adoption-learning-report.json"

    payload = write_adoption_learning_report_artifacts(matrix_json=matrix_json, out=out)

    markdown = out.with_suffix(".md")
    assert out.is_file()
    assert markdown.is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION
    rendered = markdown.read_text(encoding="utf-8")
    assert "# SDETKit adoption learning report" in rendered
    assert "input_digest:" in rendered
    assert "matrix_schema_accepted: true" in rendered
    assert "repo_memory_profile_schema_accepted: true" in rendered
    assert payload["candidate_count"] == 3


def test_adoption_learning_report_cli_dispatch(tmp_path: Path, capsys) -> None:
    matrix_json = _matrix(tmp_path / "matrix.json")
    out = tmp_path / "reports" / "adoption-learning-report.json"

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "adoption-learning-report",
            "--matrix-json",
            str(matrix_json),
            "--out",
            str(out),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert "# SDETKit adoption learning report" in stdout
    assert "safe_to_patch: false" in stdout
    assert out.is_file()
    assert out.with_suffix(".md").is_file()


def test_adoption_learning_report_attaches_non_authorizing_repo_memory_profile(
    tmp_path: Path,
) -> None:
    matrix_json = _matrix(tmp_path / "matrix.json")
    repo_memory_profile = tmp_path / "repo-memory-profile.json"
    repo_memory_profile.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.repo_memory.v6",
                "profile_status": "live_proof_supported_memory",
                "memory_mode": "trusted_main_profile",
                "decision_boundary": {
                    "automation_allowed": True,
                    "patch_application_allowed": True,
                    "merge_authorized": True,
                    "semantic_equivalence_proven": True,
                },
            }
        ),
        encoding="utf-8",
    )

    payload = build_adoption_learning_report(
        matrix_json,
        repo_memory_profile=repo_memory_profile,
    )

    assert payload["rules"]["source_matrix_only"] is False
    assert payload["rules"]["repo_memory_profile_read"] is True
    assert payload["rules"]["repo_memory_profile_authoritative"] is False
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False

    memory = payload["repo_memory_profile"]
    assert memory["connected"] is True
    assert memory["schema_version"] == "sdetkit.repo_memory.v6"
    assert memory["profile_status"] == "live_proof_supported_memory"
    assert memory["memory_mode"] == "trusted_main_profile"
    assert memory["authoritative_for_adoption_report"] is False
    assert payload["source_relationships"]["repo_memory_profile_schema_accepted"] is True
    assert memory["authority_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def test_adoption_learning_report_cli_accepts_repo_memory_profile_context(
    tmp_path: Path,
    capsys,
) -> None:
    matrix_json = _matrix(tmp_path / "matrix.json")
    repo_memory_profile = tmp_path / "repo-memory-profile.json"
    repo_memory_profile.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.repo_memory.v6",
                "profile_status": "live_proof_supported_memory",
                "memory_mode": "trusted_main_profile",
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "reports" / "adoption-learning-report.json"

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "adoption-learning-report",
            "--matrix-json",
            str(matrix_json),
            "--repo-memory-profile",
            str(repo_memory_profile),
            "--out",
            str(out),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert "## RepoMemory profile" in stdout
    assert "connected: true" in stdout
    assert "authoritative_for_adoption_report: false" in stdout

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["repo_memory_profile"]["connected"] is True
    assert payload["rules"]["repo_memory_profile_authoritative"] is False


def test_adoption_learning_provenance_binds_matrix_profile_generator_and_head(
    tmp_path: Path,
) -> None:
    matrix = _matrix(tmp_path / "matrix.json")
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps({"schema_version": ACCEPTED_REPO_MEMORY_SCHEMAS[0]}),
        encoding="utf-8",
    )
    generator = tmp_path / "generator.py"
    generator.write_text("generator-v1\n", encoding="utf-8")

    first = adoption_learning_input_provenance(
        matrix,
        root=tmp_path,
        repo_memory_profile=profile,
        generator_path=generator,
        current_head_sha="head-a",
    )
    second = adoption_learning_input_provenance(
        matrix,
        root=tmp_path,
        repo_memory_profile=profile,
        generator_path=generator,
        current_head_sha="head-a",
    )
    assert first == second
    assert first["matrix_schema_version"] == ACCEPTED_MATRIX_SCHEMA
    assert first["repo_memory_profile_schema_version"] == ACCEPTED_REPO_MEMORY_SCHEMAS[0]

    matrix_payload = json.loads(matrix.read_text(encoding="utf-8"))
    matrix_payload["repo_count"] = 11
    matrix.write_text(json.dumps(matrix_payload), encoding="utf-8")
    matrix_changed = adoption_learning_input_provenance(
        matrix,
        root=tmp_path,
        repo_memory_profile=profile,
        generator_path=generator,
        current_head_sha="head-a",
    )
    assert matrix_changed["input_digest"] != first["input_digest"]

    head_changed = adoption_learning_input_provenance(
        matrix,
        root=tmp_path,
        repo_memory_profile=profile,
        generator_path=generator,
        current_head_sha="head-b",
    )
    assert head_changed["input_digest"] != matrix_changed["input_digest"]


def test_adoption_learning_report_records_unaccepted_source_schema_relationships(
    tmp_path: Path,
) -> None:
    matrix = _matrix(tmp_path / "matrix.json")
    matrix_payload = json.loads(matrix.read_text(encoding="utf-8"))
    matrix_payload["schema_version"] = "sdetkit.adoption_real_world_learning_matrix.v0"
    matrix.write_text(json.dumps(matrix_payload), encoding="utf-8")
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps({"schema_version": "sdetkit.repo_memory.v5"}),
        encoding="utf-8",
    )

    payload = build_adoption_learning_report(
        matrix,
        repo_memory_profile=profile,
        root=tmp_path,
        current_head_sha="head-a",
    )
    relationships = payload["source_relationships"]
    assert relationships["matrix_schema_accepted"] is False
    assert relationships["repo_memory_profile_schema_accepted"] is False


def test_adoption_learning_freshness_detects_source_and_head_drift(
    tmp_path: Path,
) -> None:
    matrix = _matrix(tmp_path / "matrix.json")
    report = tmp_path / "report.json"
    write_adoption_learning_report_artifacts(
        matrix_json=matrix,
        out=report,
        root=tmp_path,
        current_head_sha="head-a",
    )

    fresh = check_adoption_learning_report_freshness(
        report_path=report,
        matrix_json=matrix,
        root=tmp_path,
        current_head_sha="head-a",
    )
    assert fresh["fresh"] is True
    assert fresh["source_schema_valid"] is True
    assert fresh["current_head_valid"] is True
    assert fresh["authority_valid"] is True

    head_stale = check_adoption_learning_report_freshness(
        report_path=report,
        matrix_json=matrix,
        root=tmp_path,
        current_head_sha="head-b",
    )
    assert head_stale["fresh"] is False
    assert head_stale["current_head_valid"] is False
    assert "current_head_sha_mismatch" in head_stale["reasons"]

    matrix_payload = json.loads(matrix.read_text(encoding="utf-8"))
    matrix_payload["repo_count"] = 12
    matrix.write_text(json.dumps(matrix_payload), encoding="utf-8")
    source_stale = check_adoption_learning_report_freshness(
        report_path=report,
        matrix_json=matrix,
        root=tmp_path,
        current_head_sha="head-a",
    )
    assert source_stale["fresh"] is False
    assert "matrix_sha256_mismatch" in source_stale["reasons"]


def test_adoption_learning_freshness_fails_closed_for_bad_reports(tmp_path: Path) -> None:
    matrix = _matrix(tmp_path / "matrix.json")
    missing = check_adoption_learning_report_freshness(
        report_path=tmp_path / "missing.json",
        matrix_json=matrix,
        root=tmp_path,
        current_head_sha="head-a",
    )
    assert missing["fresh"] is False
    assert "report_missing" in missing["reasons"]

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    invalid_result = check_adoption_learning_report_freshness(
        report_path=invalid,
        matrix_json=matrix,
        root=tmp_path,
        current_head_sha="head-a",
    )
    assert invalid_result["fresh"] is False
    assert "report_invalid_json" in invalid_result["reasons"]

    non_object = tmp_path / "non-object.json"
    non_object.write_text("[]", encoding="utf-8")
    non_object_result = check_adoption_learning_report_freshness(
        report_path=non_object,
        matrix_json=matrix,
        root=tmp_path,
        current_head_sha="head-a",
    )
    assert non_object_result["fresh"] is False
    assert "report_not_object" in non_object_result["reasons"]


def test_adoption_learning_freshness_detects_authority_drift(tmp_path: Path) -> None:
    matrix = _matrix(tmp_path / "matrix.json")
    payload = build_adoption_learning_report(
        matrix,
        root=tmp_path,
        current_head_sha="head-a",
    )
    payload["automation_allowed"] = True

    result = validate_adoption_learning_report_freshness(
        payload,
        matrix_json=matrix,
        root=tmp_path,
        current_head_sha="head-a",
    )
    assert result["fresh"] is False
    assert result["authority_valid"] is False
    assert "automation_allowed_mismatch" in result["reasons"]


def test_adoption_learning_cli_checks_freshness_without_rewriting(
    tmp_path: Path,
    capsys,
) -> None:
    from sdetkit.cli import main as cli_main

    matrix = _matrix(tmp_path / "matrix.json")
    report = tmp_path / "report.json"
    rc = cli_main(
        [
            "adoption-learning-report",
            "--root",
            ".",
            "--matrix-json",
            str(matrix),
            "--out",
            str(report),
            "--format",
            "text",
        ]
    )
    assert rc == 0
    capsys.readouterr()
    before = report.read_bytes()

    rc = cli_main(
        [
            "adoption-learning-report",
            "--root",
            ".",
            "--matrix-json",
            str(matrix),
            "--out",
            str(report),
            "--check-freshness",
            "--format",
            "text",
        ]
    )
    assert rc == 0
    stdout = capsys.readouterr().out
    assert "freshness_status=fresh" in stdout
    assert "source_schema_valid=true" in stdout
    assert "current_head_valid=true" in stdout
    assert report.read_bytes() == before
