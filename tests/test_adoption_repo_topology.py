from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_learning import build_adoption_learning_payload
from sdetkit.adoption_proof_recommendations import write_proof_recommendations_artifact
from sdetkit.adoption_repo_topology import (
    SCHEMA_VERSION,
    build_repo_topology_payload,
    render_repo_topology_text,
    write_repo_topology_artifact,
)
from sdetkit.adoption_surface import write_adoption_surface_artifact


def test_repo_topology_summarizes_current_repo_surfaces() -> None:
    payload = build_repo_topology_payload(Path("."))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert "python" in payload["topology"]["languages"]
    assert "pytest" in payload["topology"]["test_runners"]
    assert "github_actions" in payload["topology"]["ci_systems"]
    assert payload["operator_summary"]["status"] == "repo_topology_summarized"
    assert payload["operator_summary"]["has_ci"] is True
    assert payload["manual_proof_sequence"]
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_repo_topology_preserves_review_first_unknowns_for_mixed_fixture() -> None:
    payload = build_repo_topology_payload(Path("tests/fixtures/adoption_repos/mixed_python_node"))

    assert "python" in payload["topology"]["languages"]
    assert "javascript_typescript" in payload["topology"]["languages"]
    assert payload["review_first_unknowns"] == [
        "JavaScript/TypeScript package manifest detected but test command is not proven"
    ]
    assert payload["operator_summary"]["has_review_first_unknowns"] is True


def test_repo_topology_cli_dispatch_writes_text_summary(
    tmp_path: Path,
    capsys,
) -> None:
    surface = tmp_path / "adoption-surface.json"
    proof = tmp_path / "proof-recommendations.json"
    out = tmp_path / "repo-topology.json"

    write_adoption_surface_artifact(
        repo_root=Path("tests/fixtures/adoption_repos/mixed_python_node"),
        out=surface,
    )
    write_proof_recommendations_artifact(
        repo_root=Path("tests/fixtures/adoption_repos/mixed_python_node"),
        surface_json=surface,
        out=proof,
    )

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "adoption-repo-topology",
            "--root",
            "tests/fixtures/adoption_repos/mixed_python_node",
            "--surface-json",
            str(surface),
            "--proof-json",
            str(proof),
            "--out",
            str(out),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert "adoption_repo_topology_status=summarized" in stdout
    assert "has_review_first_unknowns=true" in stdout
    assert "manual_proof_sequence:" in stdout
    assert "- patch_application_allowed=false" in stdout


def test_repo_topology_text_keeps_manual_sequence_visible() -> None:
    payload = build_repo_topology_payload(Path("."))
    text = render_repo_topology_text(payload)

    assert "manual_proof_sequence:" in text
    assert "manual_only=true" in text
    assert "auto_run_allowed=false" in text
    assert "authority_boundary:" in text


def test_repo_topology_writer_records_json(tmp_path: Path) -> None:
    out = tmp_path / "repo-topology.json"

    payload = write_repo_topology_artifact(
        repo_root=Path("tests/fixtures/adoption_repos/python_pytest_github"),
        out=out,
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert json.loads(out.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION


def test_self_learning_advances_after_repo_topology_exists() -> None:
    payload = build_adoption_learning_payload(Path("."))

    assert payload["recommended_next_upgrade"] == "adoption evidence bundle"
    assert "add repo topology summary" not in payload["learning_gaps"]
    assert "add adoption evidence bundle" in payload["learning_gaps"]
    assert payload["authority_boundary"]["automation_allowed"] is False
    assert payload["authority_boundary"]["patch_application_allowed"] is False
