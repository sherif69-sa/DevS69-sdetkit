from __future__ import annotations

import json
from pathlib import Path

from sdetkit import pr_quality_required_terminal as module
from sdetkit import pr_quality_terminal_workflows as base


def run(
    name: str,
    *,
    status: str = "completed",
    conclusion: str | None = "success",
    run_id: int = 1,
    workflow_id: int | None = None,
) -> dict:
    return {
        "id": run_id,
        "workflow_id": workflow_id if workflow_id is not None else run_id,
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "run_attempt": 1,
        "run_number": 1,
        "head_sha": "head",
        "html_url": f"https://github.com/o/r/actions/runs/{run_id}",
        "event": "pull_request",
    }


def classify(rows: list[dict], *, expected: list[str], **overrides) -> dict:
    values = {
        "expected_head_sha": "head",
        "current_head_sha": "head",
        "stable_poll_count": 2,
        "required_stable_polls": 2,
    }
    values.update(overrides)
    return module.classify_required_terminal_snapshot(
        base.normalize_workflow_runs(rows),
        expected_contexts=expected,
        **values,
    )


def test_exact_head_does_not_imply_complete_required_snapshot() -> None:
    result = classify([run("Security")], expected=["ci"])

    assert result["status"] == "incomplete"
    assert result["exact_head"] is True
    assert result["exact_head_complete"] is False
    assert result["terminal_evidence_complete"] is False
    assert result["missing_expected_contexts"] == ["ci"]
    assert result["merge_authorized"] is False


def test_missing_required_context_contract_fails_closed() -> None:
    result = module.collect_required_terminal_snapshot(
        repository="o/r",
        pr_number=7,
        head_sha="head",
        expected_contexts=[],
    )

    assert result["status"] == "incomplete"
    assert result["required_contexts_available"] is False
    assert result["collection_errors"] == ["required check contexts unavailable"]


def test_publisher_waits_for_late_required_workflow_failure(monkeypatch) -> None:
    security = run("Security", run_id=1)
    failed_ci = run("CI", conclusion="failure", run_id=2)
    responses = iter(
        [
            {"head": {"sha": "head"}},
            {"workflow_runs": [security]},
            {"head": {"sha": "head"}},
            {"workflow_runs": [security]},
            {"head": {"sha": "head"}},
            {"workflow_runs": [security, failed_ci]},
            {"head": {"sha": "head"}},
            {"workflow_runs": [security, failed_ci]},
        ]
    )
    monkeypatch.setattr(base, "_gh_api_json", lambda _path: next(responses))
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    result = module.collect_required_terminal_snapshot(
        repository="o/r",
        pr_number=7,
        head_sha="head",
        expected_contexts=["ci"],
        poll_interval_seconds=1,
        required_stable_polls=2,
    )

    assert result["status"] == "failed"
    assert result["failed_workflow_names"] == ["CI"]
    assert result["missing_expected_contexts"] == []
    assert result["stable_poll_count"] == 2
    assert result["terminal_evidence_complete"] is True


def test_terminal_failure_replaces_pending_duplicates_and_preserves_name() -> None:
    snapshot = classify(
        [run("CI", conclusion="failure", run_id=9, workflow_id=99)],
        expected=["ci"],
    )
    payload = {
        "required_contexts": ["ci"],
        "check_runs": [
            {
                "name": "ci",
                "workflow_id": 99,
                "status": "queued",
                "conclusion": "",
                "required": True,
            },
            {
                "name": "CI",
                "status": "in_progress",
                "conclusion": "",
                "required": False,
            },
        ],
    }

    merged = module.merge_required_terminal_snapshot_into_checks(payload, snapshot)

    ci_records = [
        item for item in merged["check_runs"] if base.canonical_context(item.get("name")) == "ci"
    ]
    assert len(ci_records) == 1
    assert ci_records[0]["name"] == "CI"
    assert ci_records[0]["status"] == "completed"
    assert ci_records[0]["conclusion"] == "failure"
    assert ci_records[0]["required"] is True
    assert ci_records[0]["terminal_snapshot_source"] is True
    assert merged["terminal_failed_workflow_names"] == ["CI"]
    assert merged["terminal_pending_workflow_names"] == []
    assert merged["terminal_check_snapshot_complete"] is True


def test_incomplete_blocker_lists_failed_pending_and_missing_names() -> None:
    result = classify(
        [
            run("CI", conclusion="failure"),
            run("Advanced Reference", status="in_progress", conclusion=None, run_id=2),
        ],
        expected=["ci", "maintenance-autopilot"],
    )

    merged = module.merge_required_terminal_snapshot_into_checks(
        {"check_runs": [], "required_contexts": ["ci", "maintenance-autopilot"]},
        result,
    )
    blocker = merged["check_runs"][-1]

    assert result["status"] == "incomplete"
    assert result["failed_workflow_names"] == ["CI"]
    assert result["pending_workflow_names"] == ["Advanced Reference"]
    assert result["missing_expected_contexts"] == ["maintenance-autopilot"]
    assert blocker["name"] == "PR Quality terminal workflow snapshot"
    assert "failed workflows: CI" in blocker["log"]
    assert "pending workflows: Advanced Reference" in blocker["log"]
    assert "missing required checks: maintenance-autopilot" in blocker["log"]


def test_environment_hook_uses_required_contexts_and_writes_exact_names(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("HEAD_SHA", "head")
    monkeypatch.setenv("PR_NUMBER", "7")
    monkeypatch.setenv("GH_TOKEN", "token")
    expected_snapshot = classify(
        [run("maintenance-autopilot", status="queued", conclusion=None)],
        expected=["ci", "maintenance-autopilot"],
    )
    captured: dict = {}

    def fake_collect(**kwargs):
        captured.update(kwargs)
        return expected_snapshot

    monkeypatch.setattr(module, "collect_required_terminal_snapshot", fake_collect)
    checks = tmp_path / "checks.json"
    checks.write_text(
        json.dumps(
            {
                "check_runs": [],
                "required_contexts": ["ci", "maintenance-autopilot"],
            }
        ),
        encoding="utf-8",
    )

    result = module.collect_and_merge_terminal_snapshot_from_environment(
        checks_json=checks,
        out_dir=tmp_path / "out",
    )
    merged = json.loads(checks.read_text(encoding="utf-8"))

    assert result == expected_snapshot
    assert captured["expected_contexts"] == ["ci", "maintenance-autopilot"]
    assert merged["terminal_pending_workflow_names"] == ["maintenance-autopilot"]
    assert merged["terminal_missing_required_contexts"] == ["ci"]
    assert merged["terminal_check_snapshot_complete"] is False


def test_failed_check_collection_routes_through_required_terminal_layer() -> None:
    from sdetkit import failed_check_log_collection

    assert (
        failed_check_log_collection.collect_and_merge_terminal_snapshot_from_environment
        is module.collect_and_merge_terminal_snapshot_from_environment
    )
