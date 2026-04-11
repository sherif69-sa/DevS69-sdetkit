from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_project(project: Path) -> None:
    (project / "data").mkdir(parents=True, exist_ok=True)
    (project / "data" / "orders.csv").write_text(
        "id,status,amount\nA1,ok,10\nA2,ok,20\n", encoding="utf-8"
    )
    (project / "data" / "snapshot.json").write_text(
        json.dumps([{"entity_id": "A1"}, {"entity_id": "A2"}], indent=2), encoding="utf-8"
    )
    (project / "rules.json").write_text(
        json.dumps(
            {
                "files": {
                    "orders.csv": {
                        "required_columns": ["id", "status", "amount"],
                        "key_columns": ["id"],
                        "id_column": "id",
                        "expected_ids": ["A1", "A2"],
                    },
                    "snapshot.json": {
                        "id_column": "entity_id",
                    },
                },
                "cross_file_rules": [
                    {
                        "name": "orders_covered",
                        "left_file": "orders.csv",
                        "left_id_column": "id",
                        "right_file": "snapshot.json",
                        "right_id_column": "entity_id",
                        "mode": "left_subset",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (project / "inspect-project.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "scopes": [
                        {
                            "name": "core-data",
                            "include": ["data/orders.csv", "data/snapshot.json"],
                        }
                    ]
                },
                "rules": {"rules_file": "rules.json"},
                "compare": {
                    "baseline": "latest_vs_previous",
                    "thresholds": {
                        "id_drift_files": 0,
                        "schema_drift_files": 0,
                    },
                },
                "precedence": {"weights": {"compare_threshold": 5, "compare_drift": 10}},
                "outputs": {"scope_dir": "dataset-scopes"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_inspect_project_cli_repeat_is_stable(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    workspace = tmp_path / "workspace"
    out = tmp_path / "out"
    _write_project(project)

    cmd = [
        sys.executable,
        "-m",
        "sdetkit",
        "inspect-project",
        str(project),
        "--workspace-root",
        str(workspace),
        "--out-dir",
        str(out),
        "--format",
        "json",
    ]

    first = subprocess.run(cmd, text=True, capture_output=True)
    assert first.returncode == 0
    payload1 = json.loads(first.stdout)
    manifest1 = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert payload1["workflow"] == "inspect-project"
    assert payload1["ok"] is True
    assert payload1["judgment"]["schema_version"] == "sdetkit.judgment.v1"
    assert manifest1["scopes"][0]["scope"] == "core-data"

    second = subprocess.run(cmd, text=True, capture_output=True)
    assert second.returncode == 0
    payload2 = json.loads(second.stdout)
    assert payload1["workspace"]["run_hash"] == payload2["workspace"]["run_hash"]


def test_inspect_project_detects_compare_drift(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    workspace = tmp_path / "workspace"
    out = tmp_path / "out"
    _write_project(project)

    base_cmd = [
        sys.executable,
        "-m",
        "sdetkit",
        "inspect-project",
        str(project),
        "--workspace-root",
        str(workspace),
        "--out-dir",
        str(out),
        "--format",
        "json",
    ]
    first = subprocess.run(base_cmd, text=True, capture_output=True)
    assert first.returncode == 0

    (project / "data" / "orders.csv").write_text(
        "id,status,amount\nA1,ok,10\nA2,ok,20\nA3,new,30\n", encoding="utf-8"
    )

    second = subprocess.run(base_cmd, text=True, capture_output=True)
    assert second.returncode == 2
    payload = json.loads(second.stdout)
    assert payload["summary"]["compare_fail_scopes"] == 1
    assert any(item["kind"] == "compare_threshold" for item in payload["findings"])
    scope_manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert scope_manifest["compare"]
