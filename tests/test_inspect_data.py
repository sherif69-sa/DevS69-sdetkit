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


def test_inspect_applies_file_rules_and_emits_deterministic_evidence(tmp_path: Path) -> None:
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "id,status\n"
        "A1,ok\n"
        "A1,ok\n"
        "A2,pending\n",
        encoding="utf-8",
    )
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        json.dumps(
            {
                "files": {
                    "orders.csv": {
                        "required_columns": ["id", "status", "amount"],
                        "key_columns": ["id"],
                        "schema_expectations": {"status": ["numeric_string"]},
                        "id_column": "id",
                        "expected_ids": ["A1", "A2", "A3"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    rc = inspect_data.main(
        [
            str(csv_path),
            "--format",
            "json",
            "--rules",
            str(rules_path),
            "--out-dir",
            str(tmp_path / "out"),
        ]
    )
    assert rc == 2
    payload = json.loads((tmp_path / "out" / "inspect.json").read_text(encoding="utf-8"))
    report = payload["file_reports"][0]
    assert payload["summary"]["diagnostics"]["failed_rule_checks"] >= 1
    assert any(item["rule_type"] == "required_columns" and item["ok"] is False for item in report["rule_checks"])
    assert any(item["rule_type"] == "duplicate_keys" and item["ok"] is False for item in report["rule_checks"])
    assert any(item["signal"] == "duplicate_key" for item in report["suspicious_record_evidence"])


def test_inspect_applies_cross_file_rules(tmp_path: Path) -> None:
    left = tmp_path / "events.csv"
    left.write_text("id,type\nA1,open\nA2,open\n", encoding="utf-8")
    right = tmp_path / "snapshot.csv"
    right.write_text("entity_id,state\nA1,active\n", encoding="utf-8")
    rules = tmp_path / "inspect-rules.json"
    rules.write_text(
        json.dumps(
            {
                "files": {
                    "events.csv": {"id_column": "id"},
                    "snapshot.csv": {"id_column": "entity_id"},
                },
                "cross_file_rules": [
                    {
                        "name": "events_covered_by_snapshot",
                        "left_file": "events.csv",
                        "left_id_column": "id",
                        "right_file": "snapshot.csv",
                        "right_id_column": "entity_id",
                        "mode": "left_subset",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    rc = inspect_data.main([str(tmp_path), "--rules", str(rules), "--out-dir", str(tmp_path / "artifacts")])
    assert rc == 2
    payload = json.loads((tmp_path / "artifacts" / "inspect.json").read_text(encoding="utf-8"))
    assert payload["summary"]["diagnostics"]["failed_rule_checks"] >= 1
    assert len(payload["cross_file_rule_checks"]) == 1
    check = payload["cross_file_rule_checks"][0]
    assert check["name"] == "events_covered_by_snapshot"
    assert check["ok"] is False
    assert check["left_only_count"] == 1


def test_inspect_rejects_invalid_rules_mode(tmp_path: Path) -> None:
    data = tmp_path / "events.csv"
    data.write_text("id,type\nA1,open\n", encoding="utf-8")
    rules = tmp_path / "invalid-rules.json"
    rules.write_text(
        json.dumps(
            {
                "files": {"events.csv": {"id_column": "id"}},
                "cross_file_rules": [{"name": "bad", "mode": "sideways"}],
            }
        ),
        encoding="utf-8",
    )

    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "inspect",
            str(data),
            "--rules",
            str(rules),
        ],
        text=True,
        capture_output=True,
    )
    assert run.returncode == 2
    assert run.stdout == ""
    assert (
        "inspect: invalid cross_file_rules[0].mode: 'sideways'; supported values: exact_match, left_subset"
        in run.stderr
    )
