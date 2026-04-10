from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sdetkit import inspect_data


def test_inspect_single_csv_reports_findings(tmp_path: Path) -> None:
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "id,amount,status\n"
        "100,10,ok\n"
        "100,10,ok\n"
        "101,,ok\n"
        "102, 11,pending\n",
        encoding="utf-8",
    )

    rc = inspect_data.main([str(csv_path), "--format", "json", "--out-dir", str(tmp_path / "out")])
    assert rc == 2

    payload = json.loads((tmp_path / "out" / "inspect.json").read_text(encoding="utf-8"))
    assert payload["summary"]["files_analyzed"] == 1
    assert payload["summary"]["diagnostics"]["duplicate_row_groups"] == 1
    assert payload["summary"]["diagnostics"]["missing_value_columns"] >= 1
    assert payload["summary"]["diagnostics"]["duplicate_record_ids"] == 1
    assert payload["workflow"] == "inspect"
    assert payload["tool"] == "sdetkit"


def test_inspect_folder_detects_cross_file_id_mismatch(tmp_path: Path) -> None:
    events = tmp_path / "events.json"
    events.write_text(
        json.dumps(
            [
                {"id": "A1", "event": "opened"},
                {"id": "A2", "event": "closed"},
            ]
        ),
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot.csv"
    snapshot.write_text("id,state\nA1,active\nA3,inactive\n", encoding="utf-8")

    rc = inspect_data.main([str(tmp_path), "--out-dir", str(tmp_path / "artifacts")])
    assert rc == 2

    payload = json.loads((tmp_path / "artifacts" / "inspect.json").read_text(encoding="utf-8"))
    assert payload["summary"]["files_analyzed"] == 2
    assert payload["summary"]["diagnostics"]["cross_file_mismatches"] == 1
    mismatch = payload["cross_file_mismatches"][0]
    assert mismatch["left_only_count"] == 1
    assert mismatch["right_only_count"] == 1


def test_cli_inspect_command_executes(tmp_path: Path) -> None:
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps([{"id": 1, "x": "ok"}]), encoding="utf-8")

    run = subprocess.run(
        [sys.executable, "-m", "sdetkit", "inspect", str(path), "--format", "json"],
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0
    payload = json.loads(run.stdout)
    assert payload["ok"] is True
    assert payload["summary"]["files_analyzed"] == 1
