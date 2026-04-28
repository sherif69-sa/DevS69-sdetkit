from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "business_execution_start.py"
_SPEC = importlib.util.spec_from_file_location("business_execution_start_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
business_execution_start = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(business_execution_start)


def test_build_payload_has_expected_shape() -> None:
    payload = business_execution_start.build_payload(
        start_date=business_execution_start.date.fromisoformat("2026-04-28"),
        program_owner="program",
        gtm_owner="gtm",
        commercial_owner="commercial",
        solutions_owner="solutions",
        ops_owner="ops",
    )
    assert payload["schema_version"] == "sdetkit.business-execution-start.v1"
    assert payload["owners"]["program_owner"] == "program"
    assert len(payload["kpi_baseline_template"]) == 6
    assert payload["status"] == "go"
    assert "next_action" in payload


def test_main_writes_artifacts(tmp_path: Path) -> None:
    target_json = tmp_path / "week1.json"
    target_memo = tmp_path / "week1.md"
    rc = business_execution_start.main(
        [
            "--start-date",
            "2026-04-28",
            "--program-owner",
            "Alice",
            "--gtm-owner",
            "Bob",
            "--out-json",
            str(target_json),
            "--out-memo",
            str(target_memo),
        ]
    )
    assert rc == 0
    payload = json.loads(target_json.read_text(encoding="utf-8"))
    assert payload["start_date"] == "2026-04-28"
    assert payload["status"] == "needs-owner-assignment"
    memo = target_memo.read_text(encoding="utf-8")
    assert "Day 1" in memo
    assert "Status: NEEDS-OWNER-ASSIGNMENT" in memo


def test_main_strict_owner_assignment_fails_when_unassigned(tmp_path: Path) -> None:
    target_json = tmp_path / "week1.json"
    target_memo = tmp_path / "week1.md"
    rc = business_execution_start.main(
        [
            "--out-json",
            str(target_json),
            "--out-memo",
            str(target_memo),
            "--strict-owner-assignment",
        ]
    )
    assert rc == 2


def test_main_single_operator_assigns_all_owners(tmp_path: Path) -> None:
    target_json = tmp_path / "week1.json"
    target_memo = tmp_path / "week1.md"
    rc = business_execution_start.main(
        [
            "--start-date",
            "2026-04-28",
            "--single-operator",
            "Sherif",
            "--out-json",
            str(target_json),
            "--out-memo",
            str(target_memo),
        ]
    )
    assert rc == 0
    payload = json.loads(target_json.read_text(encoding="utf-8"))
    assert payload["status"] == "go"
    assert set(payload["owners"].values()) == {"Sherif"}
