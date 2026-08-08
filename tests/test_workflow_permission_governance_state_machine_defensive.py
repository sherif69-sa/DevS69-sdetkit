from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import workflow_permission_governance_state_machine as state_machine


def _control() -> dict[str, object]:
    return {
        "review_id": "permission-review-example",
        "workflow": ".github/workflows/example.yml",
        "workflow_sha256": "workflow-digest-fixture",
        "permission_group": "repository_mutation",
        "human_decision_recorded": True,
        "human_decision": "split",
        "decision_record_ref": "docs/ci/workflow-permission-decisions/example.decision.json",
        "safe_to_patch": False,
        "authority_boundary": state_machine.authority_boundary(),
    }


def test_index_and_dict_helpers_fail_closed_on_malformed_shapes() -> None:
    assert state_machine._dict_items({"not": "a-list"}) == []

    indexed, missing = state_machine._index_by_review_id(
        [
            {"workflow": ".github/workflows/missing-id.yml"},
            {"review_id": "", "workflow": ".github/workflows/blank-id.yml"},
            {"review_id": "review-ok", "workflow": ".github/workflows/ok.yml"},
        ]
    )

    assert sorted(indexed) == ["review-ok"]
    assert missing == [
        ".github/workflows/blank-id.yml",
        ".github/workflows/missing-id.yml",
    ]


def test_packet_binding_reports_malformed_boundary_and_authority() -> None:
    control = _control()
    packet = {
        **control,
        "workflow": ".github/workflows/different.yml",
        "decision_boundary": [],
        "safe_to_patch": True,
        "authority_boundary": {"workflow_mutation_allowed": True},
    }

    reasons = state_machine._packet_binding_reasons(control, packet)

    assert "packet_binding_mismatch:workflow" in reasons
    assert "packet_decision_boundary_missing" in reasons
    assert "packet_safe_to_patch_not_false" in reasons
    assert "packet_authority_boundary_invalid" in reasons


def test_packet_binding_reports_human_decision_state_mismatches() -> None:
    control = _control()
    packet = {
        **control,
        "decision_boundary": {
            "human_decision_recorded": False,
            "current_human_decision": "reduce",
            "decision_record_ref": "docs/ci/workflow-permission-decisions/other.decision.json",
        },
    }

    reasons = state_machine._packet_binding_reasons(control, packet)

    assert "packet_decision_state_mismatch" in reasons
    assert "packet_human_decision_mismatch" in reasons
    assert "packet_decision_record_ref_mismatch" in reasons


def test_plan_binding_reports_malformed_binding_and_unsafe_flags() -> None:
    control = _control()
    plan = {
        **control,
        "permission_group": "different_group",
        "decision_binding": [],
        "ready_for_patch": True,
        "safe_to_patch": True,
        "authority_boundary": {"patch_application_allowed": True},
    }

    reasons = state_machine._plan_binding_reasons(control, plan)

    assert "plan_binding_mismatch:permission_group" in reasons
    assert "plan_decision_binding_missing" in reasons
    assert "plan_ready_for_patch_not_false" in reasons
    assert "plan_safe_to_patch_not_false" in reasons
    assert "plan_authority_boundary_invalid" in reasons


def test_plan_binding_reports_decision_and_record_mismatches() -> None:
    control = _control()
    plan = {
        **control,
        "decision_binding": {
            "decision": "reduce",
            "decision_record_ref": "docs/ci/workflow-permission-decisions/other.decision.json",
        },
        "ready_for_patch": False,
        "safe_to_patch": False,
        "authority_boundary": state_machine.authority_boundary(),
    }

    reasons = state_machine._plan_binding_reasons(control, plan)

    assert "plan_binding_mismatch:decision" in reasons
    assert "plan_binding_mismatch:decision_record_ref" in reasons


def test_load_json_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a JSON object"):
        state_machine._load_json(path)


def test_safe_output_path_allows_explicit_external_destination(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    external = tmp_path / "external" / "state.json"

    assert state_machine._safe_output_path(repository_root, external) == external.resolve()


def test_renderers_cover_defensive_shapes_and_reasons() -> None:
    state_text = state_machine.render_state_text(
        {
            "status": "human_action_required",
            "summary": [],
            "bundle_digest": "bundle-digest-fixture",
            "lifecycle": [
                {
                    "workflow": ".github/workflows/example.yml",
                    "lifecycle_state": "pending_human_review",
                    "next_human_action": "complete_human_permission_review",
                }
            ],
        }
    )
    validation_text = state_machine.render_validation_text(
        {
            "status": "stale",
            "fresh": False,
            "reasons": ["bundle_digest_mismatch"],
            "current_bundle_digest": "current-bundle-fixture",
        }
    )

    assert "workflow_count=0" in state_text
    assert "example.yml: pending_human_review -> complete_human_permission_review" in state_text
    assert "fresh=false" in validation_text
    assert "reason_count=1" in validation_text
    assert "reason=bundle_digest_mismatch" in validation_text


def test_check_index_cli_fresh_and_stale_exit_contracts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    retained = tmp_path / "build" / "sdetkit" / "state.json"
    retained.parent.mkdir(parents=True)
    retained.write_text(json.dumps({"schema_version": state_machine.SCHEMA_VERSION}), encoding="utf-8")

    fresh = {
        "status": "fresh",
        "fresh": True,
        "reasons": [],
        "current_bundle_digest": "current-bundle-fixture",
        "authority_boundary": state_machine.authority_boundary(),
    }
    monkeypatch.setattr(
        state_machine,
        "validate_workflow_permission_governance_state_machine",
        lambda _root, _payload: fresh,
    )

    assert (
        state_machine.main(
            [
                "--root",
                str(tmp_path),
                "--check-index",
                "build/sdetkit/state.json",
                "--fail-on-stale",
                "--format",
                "json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["fresh"] is True

    stale = {
        **fresh,
        "status": "stale",
        "fresh": False,
        "reasons": ["input_digest_mismatch"],
    }
    monkeypatch.setattr(
        state_machine,
        "validate_workflow_permission_governance_state_machine",
        lambda _root, _payload: stale,
    )

    assert (
        state_machine.main(
            [
                "--root",
                str(tmp_path),
                "--check-index",
                "build/sdetkit/state.json",
                "--fail-on-stale",
                "--format",
                "text",
            ]
        )
        == 1
    )
    assert "reason=input_digest_mismatch" in capsys.readouterr().out
