from __future__ import annotations

import json

import pytest

from sdetkit.investigation_outcome_memory import (
    append_investigation_outcome_memory,
    build_investigation_outcome_record,
    load_investigation_outcome_memory,
    summarize_investigation_outcome_memory,
)


def test_build_investigation_outcome_record_normalizes_fields():
    record = build_investigation_outcome_record(
        classification=" PRE_COMMIT_FORMAT_DRIFT ",
        surface=" tests ",
        affected_files=["tests/test_b.py", "tests/test_a.py", "tests/test_a.py", ""],
        proof_command=" python -m pre_commit run -a ",
        safe_fix_outcome=" manual_success ",
        manual_fix_outcome=" merged ",
        pr_number="1175",
        merged=True,
        time_to_green_seconds="42",
    )

    assert record == {
        "classification": "PRE_COMMIT_FORMAT_DRIFT",
        "surface": "tests",
        "affected_files": ["tests/test_a.py", "tests/test_b.py"],
        "proof_command": "python -m pre_commit run -a",
        "safe_fix_outcome": "manual_success",
        "manual_fix_outcome": "merged",
        "pr_number": 1175,
        "merged": True,
        "time_to_green_seconds": 42,
    }


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"classification": " "}, "classification is required"),
        ({"surface": " "}, "surface is required"),
        ({"proof_command": " "}, "proof_command is required"),
    ],
)
def test_build_investigation_outcome_record_rejects_required_blank_fields(kwargs, message):
    values = {
        "classification": "MISSING_PUBLIC_API_PARITY",
        "surface": "netclient",
        "proof_command": "python -m pytest -q tests/test_netclient.py",
    }
    values.update(kwargs)

    with pytest.raises(OSError, match=message):
        build_investigation_outcome_record(**values)


def test_load_missing_memory_returns_empty_diagnostic_payload(tmp_path):
    payload = load_investigation_outcome_memory(tmp_path / "missing.json")

    assert payload == {
        "schema_version": "sdetkit.investigation.outcome_memory.v1",
        "diagnostic_only": True,
        "automation_allowed": False,
        "records": [],
    }


def test_append_investigation_outcome_memory_writes_and_sorts_records(tmp_path):
    path = tmp_path / "memory" / "investigation-outcomes.json"
    later = build_investigation_outcome_record(
        classification="PRODUCT_LOGIC_FAILURE",
        surface="release_room",
        proof_command="python -m pytest -q tests/test_release_room.py",
        pr_number=1200,
    )
    earlier = build_investigation_outcome_record(
        classification="MISSING_PUBLIC_API_PARITY",
        surface="netclient",
        proof_command="python -m pytest -q tests/test_netclient.py",
        pr_number=1175,
        merged=True,
        manual_fix_outcome="merged",
    )

    append_investigation_outcome_memory(path, later)
    payload = append_investigation_outcome_memory(path, earlier)

    assert path.exists()
    assert [record["classification"] for record in payload["records"]] == [
        "MISSING_PUBLIC_API_PARITY",
        "PRODUCT_LOGIC_FAILURE",
    ]
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written == payload
    assert written["diagnostic_only"] is True
    assert written["automation_allowed"] is False


def test_load_populated_memory_preserves_records(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "old",
                "diagnostic_only": False,
                "automation_allowed": True,
                "records": [
                    {
                        "classification": "BROKEN_TEST_DOUBLE",
                        "surface": "tests",
                        "proof_command": "python -m pytest -q tests/test_example.py",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = load_investigation_outcome_memory(path)

    assert payload["schema_version"] == "sdetkit.investigation.outcome_memory.v1"
    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["records"][0]["classification"] == "BROKEN_TEST_DOUBLE"


def test_summarize_investigation_outcome_memory_counts_records():
    memory = {
        "records": [
            {
                "classification": "PRE_COMMIT_FORMAT_DRIFT",
                "merged": True,
                "manual_fix_outcome": "merged",
                "safe_fix_outcome": "manual_success",
            },
            {
                "classification": "MISSING_PUBLIC_API_PARITY",
                "merged": True,
                "manual_fix_outcome": "merged",
                "safe_fix_outcome": "not_attempted",
            },
            {
                "classification": "PRODUCT_LOGIC_FAILURE",
                "merged": False,
                "manual_fix_outcome": "unknown",
                "safe_fix_outcome": "not_attempted",
            },
        ]
    }

    summary = summarize_investigation_outcome_memory(memory)

    assert summary == {
        "schema_version": "sdetkit.investigation.outcome_memory.summary.v1",
        "diagnostic_only": True,
        "automation_allowed": False,
        "record_count": 3,
        "merged_count": 2,
        "manual_success_count": 2,
        "safe_fix_success_count": 1,
        "classifications": [
            "MISSING_PUBLIC_API_PARITY",
            "PRE_COMMIT_FORMAT_DRIFT",
            "PRODUCT_LOGIC_FAILURE",
        ],
    }
