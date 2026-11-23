from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_main_ci_has_independent_hourly_safety_trigger_without_write_access():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    events = workflow.get("on", workflow.get(True))
    assert events["push"]["branches"] == ["main"]
    assert "pull_request" in events
    assert "workflow_dispatch" in events
    assert events["schedule"] == [{"cron": "17 * * * *"}]
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {"group": "ci-${{ github.ref }}", "cancel-in-progress": True}
    for job in workflow["jobs"].values():
        assert "schedule" not in str(job.get("if", ""))
        assert not any(value == "write" for value in job.get("permissions", {}).values())
