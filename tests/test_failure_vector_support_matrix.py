from __future__ import annotations

import json
from pathlib import Path

MATRIX_PATH = Path("docs/contracts/failure-vector-support-matrix.v1.json")
DOC_PATH = Path("docs/failure-vector-support-matrix.md")

EXPECTED_CLASSES = {
    "test",
    "formatter_only",
    "lint",
    "type",
    "dependency",
    "merge_conflict",
    "unknown",
}


def test_failure_vector_support_matrix_contract_is_complete() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "sdetkit.failure_vector.support_matrix.v1"
    assert payload["roadmap_lane"] == "Wave A / FailureVectorEngine"
    assert payload["next_lane_after_completion"] == "Wave B / SafetyGate policy expansion"

    rows = payload["supported_failure_classes"]
    classes = {row["failure_class"] for row in rows}

    assert classes == EXPECTED_CLASSES

    for row in rows:
        assert row["default_risk"] in {"low", "medium", "high"}
        assert row["review_policy"]
        assert row["first_signal_contract"]
        assert row["artifact_coverage"]


def test_failure_vector_support_matrix_blocks_roadmap_loops() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

    blocked_items = {item["item"] for item in payload["blocked_until_future_wave"]}

    assert "SafetyGate policy expansion" in blocked_items
    assert "TrajectoryStore / RepoMemory expansion" in blocked_items
    assert "cloud, service, dashboard, or worker orchestration" in blocked_items


def test_failure_vector_support_matrix_markdown_matches_contract() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    markdown = DOC_PATH.read_text(encoding="utf-8")

    assert "FailureVector support matrix" in markdown
    assert "docs/contracts/failure-vector-support-matrix.v1.json" in markdown
    assert "Do not repeat completed work" in markdown

    for row in payload["supported_failure_classes"]:
        assert f"`{row['failure_class']}`" in markdown
