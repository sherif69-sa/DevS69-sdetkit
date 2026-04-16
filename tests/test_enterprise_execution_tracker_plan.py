from __future__ import annotations

import json
from pathlib import Path


def test_enterprise_execution_tracker_has_required_shape():
    path = Path("plans/enterprise-reliability-execution-tracker.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "sdetkit.enterprise.execution-tracker.v1"
    assert isinstance(payload.get("phases"), list)
    assert payload["phases"]

    valid_status = {"pending", "in_progress", "completed"}
    for phase in payload["phases"]:
        assert phase["status"] in valid_status
        tasks = phase.get("tasks", [])
        assert isinstance(tasks, list) and tasks
        for task in tasks:
            assert task["status"] in valid_status
            assert task.get("owner")
            assert task.get("deliverable")
