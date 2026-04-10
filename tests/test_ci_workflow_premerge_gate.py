from __future__ import annotations

from pathlib import Path

import yaml


def test_fast_ci_workflow_runs_premerge_changed_files_gate_for_pull_requests() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["fast-ci"]["steps"]
    premerge_steps = [
        step
        for step in steps
        if isinstance(step, dict) and step.get("name") == "Pre-merge changed-files strict gate"
    ]
    assert len(premerge_steps) == 1
    step = premerge_steps[0]
    assert step.get("if") == "${{ github.event_name == 'pull_request' }}"
    assert step.get("run") == "bash quality.sh premerge"
    assert step.get("env", {}).get("QUALITY_DIFF_BASE") == "${{ github.event.pull_request.base.sha }}"
