from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_evidence_bundle import (
    SCHEMA_VERSION,
    build_adoption_evidence_bundle_payload,
    render_adoption_evidence_bundle_text,
    write_adoption_evidence_bundle_artifact,
)
from sdetkit.adoption_learning import build_adoption_learning_payload
from sdetkit.adoption_proof_recommendations import write_proof_recommendations_artifact
from sdetkit.adoption_repo_topology import write_repo_topology_artifact
from sdetkit.adoption_surface import write_adoption_surface_artifact


def test_evidence_bundle_collects_all_adoption_components() -> None:
    payload = build_adoption_evidence_bundle_payload(Path("."))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["bundle_status"] == "adoption_evidence_bundle_generated"
    assert payload["components"]["surface_profile"]["present"] is True
    assert payload["components"]["proof_recommendations"]["present"] is True
    assert payload["components"]["repo_topology"]["present"] is True
    assert payload["components"]["learning"]["present"] is True
    assert payload["operator_summary"]["status"] == "ready_for_human_review"
    assert payload["operator_summary"]["manual_proof_step_count"] >= 1
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_evidence_bundle_preserves_review_first_unknowns_for_mixed_fixture() -> None:
    payload = build_adoption_evidence_bundle_payload(
        Path("tests/fixtures/adoption_repos/mixed_python_node")
    )

    assert payload["operator_summary"]["review_first_count"] == 1
    assert payload["evidence"]["surface"]["review_first_unknowns"] == [
        "JavaScript/TypeScript package manifest detected but test command is not proven"
    ]
    assert payload["rules"]["bundle_only"] is True
    assert payload["rules"]["no_auto_execution"] is True


def test_evidence_bundle_cli_dispatch_writes_text_summary(
    tmp_path: Path,
    capsys,
) -> None:
    surface = tmp_path / "adoption-surface.json"
    proof = tmp_path / "proof-recommendations.json"
    topology = tmp_path / "repo-topology.json"
    out = tmp_path / "evidence-bundle.json"

    root = Path("tests/fixtures/adoption_repos/mixed_python_node")
    write_adoption_surface_artifact(repo_root=root, out=surface)
    write_proof_recommendations_artifact(
        repo_root=root,
        surface_json=surface,
        out=proof,
    )
    write_repo_topology_artifact(
        repo_root=root,
        surface_json=surface,
        proof_json=proof,
        out=topology,
    )

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "adoption-evidence-bundle",
            "--root",
            str(root),
            "--surface-json",
            str(surface),
            "--proof-json",
            str(proof),
            "--topology-json",
            str(topology),
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
    assert "adoption_evidence_bundle_status=generated" in stdout
    assert "review_first_count=1" in stdout
    assert "- no_target_repo_mutation=true" in stdout
    assert "- patch_application_allowed=false" in stdout


def test_evidence_bundle_text_keeps_authority_boundary_visible() -> None:
    payload = build_adoption_evidence_bundle_payload(Path("."))
    text = render_adoption_evidence_bundle_text(payload)

    assert "adoption_evidence_bundle_status=generated" in text
    assert "components:" in text
    assert "rules:" in text
    assert "- manual_only=true" in text
    assert "- automation_allowed=false" in text
    assert "- patch_application_allowed=false" in text


def test_evidence_bundle_writer_records_json(tmp_path: Path) -> None:
    out = tmp_path / "evidence-bundle.json"

    payload = write_adoption_evidence_bundle_artifact(
        repo_root=Path("tests/fixtures/adoption_repos/python_pytest_github"),
        out=out,
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert json.loads(out.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION


def test_self_learning_advances_after_evidence_bundle_exists() -> None:
    payload = build_adoption_learning_payload(Path("."))

    assert payload["recommended_next_upgrade"] == "public repo trial matrix"
    assert "add adoption evidence bundle" not in payload["learning_gaps"]
    assert "add public repo trial matrix" in payload["learning_gaps"]
    assert payload["authority_boundary"]["automation_allowed"] is False
    assert payload["authority_boundary"]["patch_application_allowed"] is False
