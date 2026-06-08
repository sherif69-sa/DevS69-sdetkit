from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_evidence_bundle import build_adoption_evidence_bundle_payload
from sdetkit.adoption_proof_recommendations import build_proof_recommendations_payload
from sdetkit.adoption_repo_topology import build_repo_topology_payload
from sdetkit.adoption_surface import write_adoption_surface_artifact


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _snapshot_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in root.rglob("*")
        if path.is_file()
    }


def _make_external_python_repo(root: Path) -> None:
    _write(
        root / ".git" / "config",
        '[remote "origin"]\n\turl = https://github.com/pallets/click.git\n',
    )
    _write(root / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(root / "requirements-test.txt", "pytest==9.0.3\n")
    _write(root / "tests" / "test_demo.py", "def test_demo():\n    assert True\n")
    _write(root / ".github" / "workflows" / "tests.yml", "name: tests\non: [push]\n")


def test_external_repo_stack_runs_against_target_without_mutating_it(tmp_path: Path) -> None:
    target = tmp_path / "external_public_repo_clone"
    artifact_root = tmp_path / "artifacts"
    _make_external_python_repo(target)

    before = _snapshot_tree(target)

    surface_path = artifact_root / "adoption-surface.json"
    write_adoption_surface_artifact(repo_root=target, out=surface_path)
    surface = json.loads(surface_path.read_text(encoding="utf-8"))
    proof = build_proof_recommendations_payload(target, surface_payload=surface)
    topology = build_repo_topology_payload(target, surface_payload=surface, proof_payload=proof)
    bundle = build_adoption_evidence_bundle_payload(
        target,
        surface_payload=surface,
        proof_payload=proof,
        topology_payload=topology,
    )

    assert _snapshot_tree(target) == before
    assert surface_path.is_file()
    assert not surface_path.is_relative_to(target)

    assert surface["repo_identity"]["is_current_sdetkit_repo"] is False
    assert surface["repo_identity"]["git_detected"] is True
    assert any(item["name"] == "python" for item in surface["detected_languages"])
    assert all(
        command["auto_run_allowed"] is False for command in surface["recommended_proof_commands"]
    )

    assert proof["rules"]["no_target_repo_mutation"] is True
    assert proof["rules"]["no_dependency_install"] is True
    assert topology["rules"]["no_target_repo_mutation"] is True
    assert bundle["rules"]["no_target_repo_mutation"] is True
    assert bundle["rules"]["no_auto_execution"] is True
    assert bundle["operator_summary"]["manual_proof_step_count"] >= 1

    for payload in [surface, proof, topology, bundle]:
        assert payload["automation_allowed"] is False
        assert payload["patch_application_allowed"] is False
        assert payload["merge_authorized"] is False
        assert payload["semantic_equivalence_proven"] is False


def test_public_trial_matrix_declares_real_external_stack_intent() -> None:
    payload = json.loads(
        Path("tests/fixtures/adoption_public_trials/public_repo_trial_matrix.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["trial_mode"] == "manual_read_only_public_repo_matrix"
    assert payload["source_code_vendored"] is False
    assert payload["dependency_install_performed"] is False
    assert payload["target_tests_executed"] is False
    assert payload["target_repo_mutated"] is False
    assert payload["target_pr_or_issue_opened"] is False
    assert payload["endorsement_claimed"] is False
    assert len(payload["trials"]) >= 3
