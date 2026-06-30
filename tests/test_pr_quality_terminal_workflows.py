from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "sdetkit" / "pr_quality_terminal_workflows.py"
)
spec = importlib.util.spec_from_file_location("pr_quality_terminal_workflows", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


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


def snapshot(rows: list[dict], **overrides) -> dict:
    values = {
        "expected_head_sha": "head",
        "current_head_sha": "head",
        "stable_poll_count": 2,
        "required_stable_polls": 2,
    }
    values.update(overrides)
    return module.classify_terminal_snapshot(
        module.normalize_workflow_runs(rows),
        **values,
    )


def test_current_pr_quality_workflow_and_publisher_are_excluded() -> None:
    rows = module.normalize_workflow_runs(
        [
            run("PR Quality Comment"),
            run("PR Quality Publisher", run_id=2),
            run("CI", run_id=3),
        ]
    )
    assert [item["name"] for item in rows] == ["CI"]


def test_pending_workflow_keeps_snapshot_incomplete() -> None:
    result = snapshot([run("CI", status="in_progress", conclusion=None)])
    assert result["status"] == "incomplete"
    assert [item["name"] for item in result["pending_workflows"]] == ["CI"]
    assert result["merge_authorized"] is False


def test_terminal_failure_enumerates_every_failed_workflow() -> None:
    result = snapshot(
        [
            run("CI", conclusion="failure"),
            run("Advanced Reference", conclusion="timed_out", run_id=2),
            run("Security", run_id=3),
        ]
    )
    assert result["status"] == "failed"
    assert [item["name"] for item in result["failed_workflows"]] == [
        "Advanced Reference",
        "CI",
    ]


def test_all_terminal_success_is_passed_but_never_authorizing() -> None:
    result = snapshot([run("CI"), run("Security", run_id=2)])
    assert result["status"] == "passed"
    assert result["reporting_only"] is True
    assert result["automation_allowed"] is False
    assert result["merge_authorized"] is False


def test_stale_head_is_reported_and_not_green() -> None:
    result = snapshot([run("CI")], current_head_sha="new-head")
    assert result["status"] == "stale"
    assert result["exact_head"] is False


def test_stability_requires_two_identical_terminal_polls() -> None:
    result = snapshot([run("CI")], stable_poll_count=1)
    assert result["status"] == "incomplete"


def test_latest_rerun_supersedes_older_failed_attempt() -> None:
    old = run("CI", conclusion="failure", run_id=1, workflow_id=99)
    new = run("CI", run_id=2, workflow_id=99)
    new["run_attempt"] = 2
    rows = module.normalize_workflow_runs([old, new])
    assert len(rows) == 1
    assert rows[0]["id"] == 2
    assert snapshot([old, new])["status"] == "passed"


def test_late_workflow_changes_stable_signature() -> None:
    first = module.workflow_signature(module.normalize_workflow_runs([run("CI")]))
    second = module.workflow_signature(
        module.normalize_workflow_runs([run("CI"), run("Late Workflow", run_id=2)])
    )
    assert first != second


def test_failed_workflows_are_merged_into_downstream_check_evidence() -> None:
    result = snapshot([run("CI", conclusion="failure")])
    merged = module.merge_terminal_snapshot_into_checks(
        {"check_runs": [], "required_contexts": ["ci"]},
        result,
    )
    assert merged["check_runs"][0]["name"] == "CI"
    assert merged["check_runs"][0]["required"] is True
    assert merged["check_runs"][0]["details_url"].endswith("/actions/runs/1")


def test_incomplete_snapshot_creates_required_synthetic_blocker() -> None:
    result = snapshot([run("CI", status="in_progress", conclusion=None)])
    merged = module.merge_terminal_snapshot_into_checks(
        {"check_runs": [], "required_contexts": []},
        result,
    )
    blocker = merged["check_runs"][-1]
    assert blocker["name"] == "PR Quality terminal workflow snapshot"
    assert blocker["conclusion"] == "failure"
    assert blocker["required"] is True
    assert "pending workflows: CI" in blocker["log"]


def test_collection_errors_fail_closed() -> None:
    result = snapshot(
        [],
        stable_poll_count=0,
        collection_errors=["GitHub API unavailable"],
    )
    assert result["status"] == "incomplete"
    merged = module.merge_terminal_snapshot_into_checks(
        {"check_runs": [], "required_contexts": []},
        result,
    )
    assert merged["check_runs"][-1]["log"] == "GitHub API unavailable"


def test_polling_waits_for_pending_then_late_failure(monkeypatch) -> None:
    responses = iter(
        [
            {"head": {"sha": "head"}},
            {"workflow_runs": [run("CI", status="in_progress", conclusion=None)]},
            {"head": {"sha": "head"}},
            {"workflow_runs": [run("CI", conclusion="failure")]},
            {"head": {"sha": "head"}},
            {"workflow_runs": [run("CI", conclusion="failure")]},
        ]
    )
    monkeypatch.setattr(module, "_gh_api_json", lambda _path: next(responses))
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    result = module.collect_terminal_workflow_snapshot(
        repository="o/r",
        pr_number=7,
        head_sha="head",
        poll_interval_seconds=1,
        required_stable_polls=2,
    )
    assert result["status"] == "failed"
    assert [item["name"] for item in result["failed_workflows"]] == ["CI"]
    assert result["stable_poll_count"] == 2


def test_environment_hook_is_disabled_outside_github_actions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    checks = tmp_path / "checks.json"
    checks.write_text(json.dumps({"check_runs": []}), encoding="utf-8")
    assert (
        module.collect_and_merge_terminal_snapshot_from_environment(
            checks_json=checks,
            out_dir=tmp_path / "out",
        )
        is None
    )
