from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_learning_report import (
    SCHEMA_VERSION,
    build_adoption_learning_report,
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
    assert "# SDETKit adoption learning report" in markdown.read_text(encoding="utf-8")
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
