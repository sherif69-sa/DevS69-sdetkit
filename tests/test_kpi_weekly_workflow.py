from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "kpi-weekly.yml"


def test_weekly_kpi_workflow_exists_and_publishes_artifact() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    on_block = workflow.get("on") if isinstance(workflow, dict) else None
    if on_block is None and isinstance(workflow, dict):
        on_block = workflow.get(True)  # YAML 1.1 can coerce "on" to bool
    assert isinstance(on_block, dict)
    assert "schedule" in on_block
    assert any("cron" in item for item in on_block["schedule"])

    job = workflow["jobs"]["kpi-pack"]
    run_blob = "\n".join(step.get("run", "") for step in job["steps"] if isinstance(step, dict))
    assert "python -m sdetkit kpi-report" in run_blob
    assert "kpi-metrics-current.json" in run_blob

    upload_steps = [
        s
        for s in job["steps"]
        if isinstance(s, dict) and "upload-artifact" in str(s.get("uses", ""))
    ]
    assert upload_steps, "expected artifact upload step"
