from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sdetkit import inspect_compare, inspect_data


def test_inspect_compare_with_two_paths_reports_drift(tmp_path: Path) -> None:
    data = tmp_path / "orders.csv"
    data.write_text("id,status\nA1,ok\nA2,ok\n", encoding="utf-8")
    inspect_data.main([str(data), "--out-dir", str(tmp_path / "left")])
    data.write_text("id,status\nA1,ok\nA2,ok\nA3,new\n", encoding="utf-8")
    inspect_data.main([str(data), "--out-dir", str(tmp_path / "right")])

    rc = inspect_compare.main(
        [
            "--left",
            str(tmp_path / "left" / "inspect.json"),
            "--right",
            str(tmp_path / "right" / "inspect.json"),
            "--format",
            "json",
            "--out-dir",
            str(tmp_path / "compare"),
            "--no-workspace",
        ]
    )

    assert rc == 2
    payload = json.loads(
        (tmp_path / "compare" / "inspect-compare.json").read_text(encoding="utf-8")
    )
    assert payload["summary"]["id_drift_files"] == 1
    assert payload["summary"]["drift_score"] >= 1
    assert payload["judgment"]["schema_version"] == "sdetkit.judgment.v1"


def test_inspect_compare_latest_vs_previous_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    out = tmp_path / "out"
    data = tmp_path / "orders.csv"

    data.write_text("id,amount\nA1,10\n", encoding="utf-8")
    inspect_data.main([str(data), "--out-dir", str(out), "--workspace-root", str(workspace)])

    data.write_text("id,amount\nA1,10\nA2,20\n", encoding="utf-8")
    inspect_data.main([str(data), "--out-dir", str(out), "--workspace-root", str(workspace)])

    rc = inspect_compare.main(
        [
            "--latest-vs-previous",
            "--scope",
            "orders.csv",
            "--workspace-root",
            str(workspace),
            "--out-dir",
            str(tmp_path / "cmp"),
            "--format",
            "json",
            "--no-workspace",
        ]
    )
    assert rc == 2
    payload = json.loads((tmp_path / "cmp" / "inspect-compare.json").read_text(encoding="utf-8"))
    assert payload["baseline"]["label"].startswith("workspace:")
    assert payload["summary"]["id_drift_files"] == 1


def test_inspect_compare_workspace_run_pair(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    data = tmp_path / "events.csv"
    out = tmp_path / "inspect-out"

    data.write_text("id,type\nA1,open\n", encoding="utf-8")
    inspect_data.main([str(data), "--out-dir", str(out), "--workspace-root", str(workspace)])
    first = json.loads((out / "inspect.json").read_text(encoding="utf-8"))["workspace"]["run_hash"]

    data.write_text("id,type\nA1,open\nA1,open\n", encoding="utf-8")
    inspect_data.main([str(data), "--out-dir", str(out), "--workspace-root", str(workspace)])
    second = json.loads((out / "inspect.json").read_text(encoding="utf-8"))["workspace"]["run_hash"]

    rc = inspect_compare.main(
        [
            "--left-run",
            first,
            "--right-run",
            second,
            "--scope",
            "events.csv",
            "--workspace-root",
            str(workspace),
            "--format",
            "json",
            "--out-dir",
            str(tmp_path / "compare"),
            "--no-workspace",
        ]
    )
    assert rc == 2
    payload = json.loads(
        (tmp_path / "compare" / "inspect-compare.json").read_text(encoding="utf-8")
    )
    assert payload["summary"]["duplicate_row_groups_delta"] == 1


def test_cli_inspect_compare_command_executes(tmp_path: Path) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    base_payload = {
        "summary": {"diagnostics": {}, "files_analyzed": 0, "total_records": 0},
        "file_reports": [],
    }
    left.write_text(json.dumps(base_payload), encoding="utf-8")
    right.write_text(json.dumps(base_payload), encoding="utf-8")

    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "inspect-compare",
            "--left",
            str(left),
            "--right",
            str(right),
            "--format",
            "json",
            "--no-workspace",
        ],
        text=True,
        capture_output=True,
    )

    assert run.returncode == 0
    payload = json.loads(run.stdout)
    assert payload["workflow"] == "inspect-compare"
    assert payload["ok"] is True
