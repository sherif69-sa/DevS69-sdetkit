from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import workflow_permission_decision_record as decision_record
from sdetkit import workflow_permission_review_session as review_session


def _packet_index() -> dict[str, object]:
    workflow = ".github/workflows/example.yml"
    workflow_sha256 = "a" * 64
    review_id = decision_record.review_id_for_workflow(workflow)
    return {
        "schema_version": "sdetkit.workflow_permission_review_packet.v1",
        "bundle_digest": "bundle-current",
        "input_provenance": {"input_digest": "input-current"},
        "packets": [
            {
                "review_id": review_id,
                "packet_digest": "packet-current",
                "workflow": workflow,
                "workflow_sha256": workflow_sha256,
                "permission_group": "repository_mutation",
                "decision_boundary": {"human_decision_recorded": False},
                "proof_contract": ["exact-head CI"],
                "rollback_contract": {
                    "strategy": "restore_exact_workflow_bytes",
                    "workflow_sha256": workflow_sha256,
                },
            }
        ],
    }


def _install_packet_index(monkeypatch) -> dict[str, object]:
    payload = _packet_index()
    monkeypatch.setattr(
        review_session,
        "build_workflow_permission_review_packet_index",
        lambda _root: payload,
    )
    return payload


def _completed_session(monkeypatch, root: Path) -> Path:
    _install_packet_index(monkeypatch)
    session = review_session.build_review_session_template(root, mode="complete")
    session["reviewer"] = "repository-owner"
    session["reviewer_evidence"] = (
        "https://github.com/sherif69-sa/DevS69-sdetkit/issues/2181#issuecomment-1"
    )
    session["decided_at"] = "2026-08-08T15:00:00+00:00"
    entry = session["entries"][0]
    entry["decision"] = "keep"
    entry["rationale"] = "I reviewed the exact workflow and chose to retain its permissions."
    entry["proposed_change"] = {"kind": "none"}
    entry["proof_acknowledged"] = True
    entry["rollback_acknowledged"] = True
    path = root / "session.json"
    path.write_text(json.dumps(session, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_main_writes_complete_template_and_json_output(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    packet_index = _install_packet_index(monkeypatch)

    result = review_session.main(
        [
            "--root",
            str(tmp_path),
            "--template-mode",
            "complete",
            "--template-out",
            "build/review-session.json",
            "--format",
            "json",
        ]
    )

    assert result == 0
    template_path = tmp_path / "build" / "review-session.json"
    assert template_path.is_file()
    template = json.loads(template_path.read_text(encoding="utf-8"))
    assert template["packet_bundle_digest"] == packet_index["bundle_digest"]
    assert len(template["entries"]) == 1
    assert template["reviewer"] is None
    output = json.loads(capsys.readouterr().out)
    assert output["template_path"] == template_path.as_posix()
    assert output["template"]["entries"][0]["decision"] is None
    assert not any(output["authority_boundary"].values())


def test_main_compiles_valid_session_to_build_and_renders_text(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    session_path = _completed_session(monkeypatch, tmp_path)

    result = review_session.main(
        [
            "--root",
            str(tmp_path),
            "--session",
            session_path.name,
            "--compile-out-dir",
            "build/compiled-decisions",
            "--fail-on-invalid",
            "--format",
            "text",
        ]
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "status=current" in output
    assert "compiled_record_count=1" in output
    assert "decision_inference_allowed=false" in output
    assert "permission_mutation_allowed=false" in output
    compiled_dir = tmp_path / "build" / "compiled-decisions"
    manifest = compiled_dir / review_session.COMPILATION_MANIFEST_NAME
    assert manifest.is_file()
    decision_files = sorted(compiled_dir.glob("*.decision.json"))
    assert len(decision_files) == 1
    decision = json.loads(decision_files[0].read_text(encoding="utf-8"))
    assert decision["decision"] == "keep"
    assert decision["reviewer"] == "repository-owner"


def test_main_invalid_session_fails_closed_without_output_records(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    session_path = _completed_session(monkeypatch, tmp_path)
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session["packet_bundle_digest"] = "stale-bundle"
    session_path.write_text(json.dumps(session, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = review_session.main(
        [
            "--root",
            str(tmp_path),
            "--session",
            session_path.name,
            "--compile-out-dir",
            "build/blocked-decisions",
            "--fail-on-invalid",
            "--format",
            "text",
        ]
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "status=stale" in output
    assert "packet_bundle_digest_mismatch" in output
    assert "compiled_record_count=0" in output
    assert not (tmp_path / "build" / "blocked-decisions").exists()


def test_main_template_text_reports_blank_human_boundary(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _install_packet_index(monkeypatch)

    result = review_session.main(
        [
            "--root",
            str(tmp_path),
            "--template-out",
            "build/review-session.json",
            "--format",
            "text",
        ]
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "template_mode=complete" in output
    assert "template_entry_count=1" in output
    assert "decision_inference_allowed=false" in output


def test_load_json_rejects_non_object_session(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="review session must be a JSON object"):
        review_session._load_json(path)


def test_safe_output_directory_resolves_relative_path_beneath_explicit_root(
    tmp_path: Path,
) -> None:
    output = review_session._safe_output_directory(
        tmp_path,
        Path("build/compiled-decisions"),
    )

    assert output == (tmp_path / "build" / "compiled-decisions").resolve()

    with pytest.raises(ValueError, match="only be written under build"):
        review_session._safe_output_directory(
            tmp_path,
            Path("docs/ci/workflow-permission-decisions"),
        )
