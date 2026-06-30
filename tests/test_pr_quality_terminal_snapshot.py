from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "scripts" / "pr_quality_terminal_model.py"
MODULE_PATH = ROOT / "scripts" / "pr_quality_terminal_snapshot.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "pr-quality-publisher.yml"
sys.path.insert(0, str(ROOT / "scripts"))

model_spec = importlib.util.spec_from_file_location(
    "pr_quality_terminal_model", MODEL_PATH
)
assert model_spec and model_spec.loader
model = importlib.util.module_from_spec(model_spec)
sys.modules[model_spec.name] = model
model_spec.loader.exec_module(model)

spec = importlib.util.spec_from_file_location(
    "pr_quality_terminal_snapshot", MODULE_PATH
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

module.build_snapshot = model.build_snapshot
module.render_comment = model.render_comment


def run(
    name: str,
    *,
    status: str = "completed",
    conclusion: str | None = "success",
    run_id: int = 1,
):
    return {
        "id": run_id,
        "workflow_id": run_id,
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "run_attempt": 1,
        "run_number": 1,
        "html_url": f"https://github.com/o/r/actions/runs/{run_id}",
        "head_sha": "head",
    }


def check(
    name: str,
    *,
    status: str = "completed",
    conclusion: str | None = "success",
    check_id: int = 1,
):
    return {
        "id": check_id,
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "details_url": f"https://github.com/o/r/runs/{check_id}",
    }


def snapshot(**overrides):
    values = {
        "repository": "o/r",
        "pr_number": 7,
        "head_sha": "head",
        "current_head_sha": "head",
        "merge_commit_sha": "merge",
        "workflow_runs": [run("CI"), run("maintenance-autopilot", run_id=2)],
        "check_runs": [],
        "statuses": [],
        "required_contexts": ["ci", "maintenance-autopilot"],
        "stable_poll_count": 2,
        "required_stable_polls": 2,
    }
    values.update(overrides)
    return module.build_snapshot(**values)


def test_race_reproduced_late_ci_failure_is_named_with_first_step() -> None:
    result = snapshot(
        workflow_runs=[
            run("CI", conclusion="failure"),
            run("maintenance-autopilot", run_id=2),
        ],
        jobs_by_run={
            1: [
                {
                    "id": 11,
                    "name": "Full CI",
                    "conclusion": "failure",
                    "html_url": "https://github.com/o/r/actions/runs/1/job/11",
                    "steps": [
                        {"name": "Install", "number": 1, "conclusion": "success"},
                        {"name": "Coverage gate", "number": 2, "conclusion": "failure"},
                    ],
                }
            ]
        },
        logs_by_job={11: "FAILED tests/test_gate.py::test_truth - AssertionError"},
    )
    assert result["review_state"] == "blocked"
    assert result["failed_workflows"][0]["workflow_name"] == "CI"
    assert result["failed_workflows"][0]["step_name"] == "Coverage gate"
    assert (
        "tests/test_gate.py::test_truth"
        in result["failed_workflows"][0]["first_failure"]
    )


def test_multiple_failures_are_all_rendered_once() -> None:
    result = snapshot(
        workflow_runs=[
            run("CI", conclusion="failure", run_id=1),
            run("Advanced Reference", conclusion="timed_out", run_id=2),
            run("maintenance-autopilot", run_id=3),
        ]
    )
    body = module.render_comment(result)
    assert body.count("CI") == 1
    assert body.count("Advanced Reference") == 1
    assert len(result["failed_workflows"]) == 2


def test_pending_timeout_is_incomplete_and_no_ship() -> None:
    result = snapshot(
        workflow_runs=[
            run("CI", status="in_progress", conclusion=None),
            run("maintenance-autopilot", run_id=2),
        ],
        stable_poll_count=0,
        timed_out=True,
    )
    assert result["snapshot_status"] == "incomplete"
    assert result["merge_readiness"] == "NO_SHIP"
    assert result["pending_workflows"][0]["name"] == "CI"


def test_missing_required_context_is_enumerated() -> None:
    result = snapshot(
        workflow_runs=[run("maintenance-autopilot", run_id=2)],
    )
    assert result["review_state"] == "waiting_or_unknown"
    assert [row["name"] for row in result["missing_required_contexts"]] == ["ci"]


def test_stale_head_refuses_ready_state() -> None:
    result = snapshot(current_head_sha="new-head")
    assert result["review_state"] == "stale"
    assert result["merge_readiness"] == "NO_SHIP"


def test_all_green_is_ready_but_never_merge_authorized() -> None:
    result = snapshot()
    assert result["review_state"] == "ready"
    assert result["merge_authorized"] is False
    assert result["pull_request_code_executed"] is False


def test_late_workflow_registration_changes_signature() -> None:
    first = snapshot(workflow_runs=[run("CI"), run("maintenance-autopilot", run_id=2)])
    second = snapshot(
        workflow_runs=[
            run("CI"),
            run("maintenance-autopilot", run_id=2),
            run("Late Workflow", status="in_progress", conclusion=None, run_id=3),
        ],
        stable_poll_count=0,
    )
    assert first["workflow_signature"] != second["workflow_signature"]
    assert second["review_state"] == "waiting_or_unknown"


def complete_alert() -> dict:
    return {
        "number": 1458,
        "state": "open",
        "dismissed_reason": None,
        "html_url": "https://github.com/o/r/security/code-scanning/1458",
        "rule": {"id": "SEC_RULE", "security_severity_level": "high"},
        "most_recent_instance": {
            "commit_sha": "head",
            "ref": "refs/heads/feature",
            "location": {"path": "src/a.py", "start_line": 8},
            "message": {"text": "Current-head finding"},
        },
    }


def test_complete_current_security_alert_blocks_with_provenance() -> None:
    result = snapshot(security_alerts=[complete_alert()])
    assert result["review_state"] == "blocked"
    assert result["security_findings"][0]["path"] == "src/a.py"
    assert not result["incomplete_security_findings"]


def test_missing_security_provenance_is_incomplete_not_actionable() -> None:
    alert = complete_alert()
    alert["most_recent_instance"]["message"] = {}
    result = snapshot(security_alerts=[alert])
    assert result["review_state"] == "waiting_or_unknown"
    assert not result["security_findings"]
    assert "message" in result["incomplete_security_findings"][0]["evidence_gaps"]


def test_stale_security_alert_cannot_be_primary() -> None:
    alert = complete_alert()
    alert["most_recent_instance"]["commit_sha"] = "old"
    alert["most_recent_instance"]["ref"] = "refs/heads/old"
    result = snapshot(security_alerts=[alert])
    assert result["review_state"] == "waiting_or_unknown"
    assert not result["security_findings"]
    assert (
        "current_head_relation"
        in result["incomplete_security_findings"][0]["evidence_gaps"]
    )


def test_latest_rerun_replaces_older_failed_attempt() -> None:
    older = run("CI", conclusion="failure", run_id=1)
    older["workflow_id"] = 99
    older["run_attempt"] = 1
    newer = run("CI", conclusion="success", run_id=2)
    newer["workflow_id"] = 99
    newer["run_attempt"] = 2
    result = snapshot(
        workflow_runs=[older, newer, run("maintenance-autopilot", run_id=3)]
    )
    assert result["review_state"] == "ready"
    assert not result["failed_workflows"]


def test_polling_waits_through_pending_then_reports_late_failure(monkeypatch) -> None:
    samples = iter(
        [
            (
                {
                    "current_head_sha": "head",
                    "merge_commit_sha": "merge",
                    "workflow_runs": [
                        run("CI", status="in_progress", conclusion=None),
                        run("maintenance-autopilot", run_id=2),
                    ],
                    "check_runs": [],
                    "statuses": [],
                    "security_alerts": [],
                    "required_contexts": ["ci", "maintenance-autopilot"],
                },
                {},
                {},
                [],
            ),
            (
                {
                    "current_head_sha": "head",
                    "merge_commit_sha": "merge",
                    "workflow_runs": [
                        run("CI", conclusion="failure"),
                        run("maintenance-autopilot", run_id=2),
                    ],
                    "check_runs": [],
                    "statuses": [],
                    "security_alerts": [],
                    "required_contexts": ["ci", "maintenance-autopilot"],
                },
                {},
                {},
                [],
            ),
            (
                {
                    "current_head_sha": "head",
                    "merge_commit_sha": "merge",
                    "workflow_runs": [
                        run("CI", conclusion="failure"),
                        run("maintenance-autopilot", run_id=2),
                    ],
                    "check_runs": [],
                    "statuses": [],
                    "security_alerts": [],
                    "required_contexts": ["ci", "maintenance-autopilot"],
                },
                {},
                {},
                [],
            ),
        ]
    )

    def fake_collect(*args, **kwargs):
        return next(samples)

    monkeypatch.setattr(module, "collect", fake_collect)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    api = module.GitHubApi(repository="o/r", token="token")
    result = module.poll(
        api,
        7,
        "head",
        ["ci", "maintenance-autopilot"],
        60,
        1,
        2,
    )
    assert result["review_state"] == "blocked"
    assert [item["workflow_name"] for item in result["failed_workflows"]] == ["CI"]
    assert result["stable_poll_count"] == 2


def test_terminal_publisher_checks_out_only_trusted_default_branch() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "ref: ${{ github.event.repository.default_branch }}" in workflow
    assert "persist-credentials: false" in workflow
    assert "security-events: read" in workflow
    assert "pull-requests: read" in workflow
    assert "pull-requests: write" not in workflow
    assert "github.event.workflow_run.head_branch" not in workflow
    assert "name: PR Quality Publisher" in workflow
    assert "scripts/pr_quality_terminal_snapshot.py" in workflow
    assert "--stable-polls 2" in workflow
    assert "merge_authorized=false" in module.render_comment(snapshot())
