from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import workflow_permission_review_handoff_bundle as handoff


def _manifest(*, status: str = "ready_for_human_handoff") -> dict[str, object]:
    return {
        "schema_version": handoff.SCHEMA_VERSION,
        "status": status,
        "summary": {
            "active_work_item_count": 1,
            "packaged_packet_count": 1,
            "artifact_count": 5,
            "blocked_reason_count": 0,
        },
        "bundle_digest": "bundle-marker",
        "global_reasons": [],
        "packet_refs": [],
        "artifact_index": [],
        "authority_boundary": handoff.authority_boundary(),
    }


def test_cli_relative_output_is_resolved_beneath_explicit_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    manifest = _manifest()
    observed: list[tuple[Path, str | Path]] = []

    monkeypatch.setattr(
        handoff,
        "build_workflow_permission_review_handoff_bundle",
        lambda _root: manifest,
    )

    def fake_write(repo_root: str | Path, out_dir: str | Path) -> dict[str, object]:
        observed.append((Path(repo_root), out_dir))
        return manifest

    monkeypatch.setattr(handoff, "write_workflow_permission_review_handoff_bundle", fake_write)

    assert (
        handoff.main(
            [
                "--root",
                str(root),
                "--out-dir",
                "build/sdetkit/reviewer-handoff",
                "--format",
                "text",
            ]
        )
        == 0
    )
    assert observed == [(root.resolve(), "build/sdetkit/reviewer-handoff")]
    text = capsys.readouterr().out
    assert "Workflow Permission Reviewer Handoff Bundle v1" in text
    assert "machine_recommendation_allowed=false" in text
    assert "merge_authorized=false" in text


def test_cli_json_output_is_machine_readable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.setattr(
        handoff,
        "build_workflow_permission_review_handoff_bundle",
        lambda _root: _manifest(),
    )

    assert handoff.main(["--root", str(tmp_path), "--format", "json"]) == 0
    rendered = json.loads(capsys.readouterr().out)

    assert rendered["schema_version"] == handoff.SCHEMA_VERSION
    assert rendered["status"] == "ready_for_human_handoff"


def test_cli_blocked_bundle_refuses_export(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    blocked = _manifest(status="blocked")
    blocked["global_reasons"] = ["packet_missing"]
    monkeypatch.setattr(
        handoff,
        "build_workflow_permission_review_handoff_bundle",
        lambda _root: blocked,
    )

    def fail_write(_root: object, _out: object) -> dict[str, object]:
        raise AssertionError("blocked CLI must not call the bundle writer")

    monkeypatch.setattr(handoff, "write_workflow_permission_review_handoff_bundle", fail_write)

    assert (
        handoff.main(
            [
                "--root",
                str(tmp_path),
                "--out-dir",
                "build/handoff",
                "--format",
                "text",
            ]
        )
        == 1
    )
    assert "status=blocked" in capsys.readouterr().out
    assert not (tmp_path / "build" / "handoff").exists()


def test_cli_check_dir_fresh_and_stale_exit_contracts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    fresh = {
        "status": "fresh",
        "fresh": True,
        "reasons": [],
        "current_bundle_digest": "bundle-marker",
        "authority_boundary": handoff.authority_boundary(),
    }
    monkeypatch.setattr(
        handoff,
        "validate_workflow_permission_review_handoff_bundle",
        lambda _root, _bundle: fresh,
    )

    assert (
        handoff.main(
            [
                "--root",
                str(tmp_path),
                "--check-dir",
                "build/handoff",
                "--fail-on-stale",
                "--format",
                "json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["fresh"] is True

    reason = "_".join(("artifact", "content", "mismatch")) + ":packets/example.json"
    stale = {
        **fresh,
        "status": "stale",
        "fresh": False,
        "reasons": [reason],
    }
    monkeypatch.setattr(
        handoff,
        "validate_workflow_permission_review_handoff_bundle",
        lambda _root, _bundle: stale,
    )

    assert (
        handoff.main(
            [
                "--root",
                str(tmp_path),
                "--check-dir",
                "build/handoff",
                "--fail-on-stale",
                "--format",
                "text",
            ]
        )
        == 1
    )
    text = capsys.readouterr().out
    assert "fresh=false" in text
    assert f"reason={reason}" in text


def test_cli_stale_without_fail_flag_is_advisory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    stale = {
        "status": "stale",
        "fresh": False,
        "reasons": ["manifest_missing"],
        "current_bundle_digest": "",
        "authority_boundary": handoff.authority_boundary(),
    }
    monkeypatch.setattr(
        handoff,
        "validate_workflow_permission_review_handoff_bundle",
        lambda _root, _bundle: stale,
    )

    assert (
        handoff.main(
            [
                "--root",
                str(tmp_path),
                "--check-dir",
                "build/handoff",
                "--format",
                "text",
            ]
        )
        == 0
    )


def test_load_json_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / handoff.MANIFEST_NAME
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a JSON object"):
        handoff._load_json(path)
