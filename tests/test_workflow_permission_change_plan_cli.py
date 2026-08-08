from __future__ import annotations

import json
from pathlib import Path

from sdetkit import workflow_permission_change_plan as change_plan

FIXTURE_DIGEST = "fixture-digest-not-a-sha"


def _index(*, status: str = "not_required") -> dict[str, object]:
    return {
        "schema_version": change_plan.SCHEMA_VERSION,
        "status": status,
        "summary": {
            "change_plan_count": 0,
            "reduce_or_split_decision_count": 0,
            "non_change_decision_count": 0,
            "pending_human_review_count": 16,
        },
        "bundle_digest": FIXTURE_DIGEST,
        "plans": [],
        "authority_boundary": change_plan.authority_boundary(),
    }


def test_main_text_reports_non_executable_live_state(monkeypatch, capsys) -> None:
    payload = _index()
    monkeypatch.setattr(
        change_plan,
        "build_workflow_permission_change_plan_index",
        lambda _root: payload,
    )

    result = change_plan.main(["--root", ".", "--format", "text"])
    output = capsys.readouterr().out

    assert result == 0
    assert "status=not_required" in output
    assert "change_plan_count=0" in output
    assert "automatic_patch_generation_allowed=false" in output
    assert "implementation_authorized=false" in output
    assert "permission_mutation_allowed=false" in output


def test_main_json_writes_relative_output_beneath_explicit_root(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    payload = _index()
    monkeypatch.setattr(
        change_plan,
        "build_workflow_permission_change_plan_index",
        lambda _root: payload,
    )

    result = change_plan.main(
        [
            "--root",
            str(tmp_path),
            "--out",
            "build/sdetkit/workflow-permission-change-plans.json",
            "--format",
            "json",
        ]
    )

    output_path = tmp_path / "build" / "sdetkit" / "workflow-permission-change-plans.json"
    assert result == 0
    assert json.loads(capsys.readouterr().out) == payload
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload


def test_main_returns_nonzero_for_blocked_plan_index(monkeypatch, capsys) -> None:
    payload = _index(status="blocked")
    monkeypatch.setattr(
        change_plan,
        "build_workflow_permission_change_plan_index",
        lambda _root: payload,
    )

    result = change_plan.main(["--format", "json"])

    assert result == 1
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"


def test_render_index_text_handles_missing_summary_shape() -> None:
    output = change_plan.render_index_text(
        {
            "status": "not_required",
            "summary": [],
            "bundle_digest": FIXTURE_DIGEST,
        }
    )

    assert "change_plan_count=0" in output
    assert "pending_human_review_count=0" in output
    assert "implementation_authorized=false" in output
