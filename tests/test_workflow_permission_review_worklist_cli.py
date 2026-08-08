from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import workflow_permission_review_worklist as worklist


def _payload(*, status: str = "human_work_required") -> dict[str, object]:
    return {
        "schema_version": worklist.SCHEMA_VERSION,
        "status": status,
        "summary": {
            "workflow_count": 1,
            "work_item_count": 1,
            "review_action_count": 1,
            "implementation_action_count": 0,
            "blocked_repair_count": 0,
        },
        "bundle_digest": "bundle-marker",
        "work_items": [
            {
                "workflow": ".github/workflows/example.yml",
                "next_human_action": "complete_human_permission_review",
                "permission_group": "repository_mutation",
            }
        ],
        "authority_boundary": worklist.authority_boundary(),
    }


def test_cli_relative_output_is_resolved_beneath_explicit_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(worklist, "build_workflow_permission_review_worklist", lambda _root: _payload())

    rc = worklist.main(
        [
            "--root",
            str(root),
            "--out",
            "build/sdetkit/worklist.json",
            "--format",
            "text",
        ]
    )

    assert rc == 0
    output = root / "build" / "sdetkit" / "worklist.json"
    assert output.is_file()
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "human_work_required"
    text = capsys.readouterr().out
    assert "Workflow Permission Review Worklist v1" in text
    assert "machine_recommendation_allowed=false" in text


def test_cli_refuses_repository_source_tree_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(worklist, "build_workflow_permission_review_worklist", lambda _root: _payload())

    with pytest.raises(ValueError, match="may only be written under build"):
        worklist.main(
            [
                "--root",
                str(root),
                "--out",
                "docs/ci/worklist.json",
            ]
        )


def test_cli_json_output_is_machine_readable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.setattr(worklist, "build_workflow_permission_review_worklist", lambda _root: _payload())

    assert worklist.main(["--root", str(tmp_path), "--format", "json"]) == 0

    rendered = json.loads(capsys.readouterr().out)
    assert rendered["schema_version"] == worklist.SCHEMA_VERSION
    assert rendered["status"] == "human_work_required"


def test_cli_blocked_live_worklist_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        worklist,
        "build_workflow_permission_review_worklist",
        lambda _root: _payload(status="blocked"),
    )

    assert worklist.main(["--root", str(tmp_path), "--format", "json"]) == 1


def test_check_index_fresh_and_stale_exit_contracts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    root = tmp_path / "repo"
    retained = root / "build" / "worklist.json"
    retained.parent.mkdir(parents=True)
    retained.write_text(json.dumps(_payload()) + "\n", encoding="utf-8")

    fresh = {
        "status": "fresh",
        "fresh": True,
        "reasons": [],
        "current_bundle_digest": "bundle-marker",
        "authority_boundary": worklist.authority_boundary(),
    }
    monkeypatch.setattr(
        worklist,
        "validate_workflow_permission_review_worklist",
        lambda _root, _payload: fresh,
    )

    assert (
        worklist.main(
            [
                "--root",
                str(root),
                "--check-index",
                "build/worklist.json",
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
        "reasons": ["bundle_digest_mismatch"],
    }
    monkeypatch.setattr(
        worklist,
        "validate_workflow_permission_review_worklist",
        lambda _root, _payload: stale,
    )

    assert (
        worklist.main(
            [
                "--root",
                str(root),
                "--check-index",
                "build/worklist.json",
                "--fail-on-stale",
                "--format",
                "text",
            ]
        )
        == 1
    )
    text = capsys.readouterr().out
    assert "fresh=false" in text
    assert "reason=bundle_digest_mismatch" in text


def test_load_json_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "worklist.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a JSON object"):
        worklist._load_json(path)
