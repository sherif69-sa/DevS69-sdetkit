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

EXPECTED_DOWNSTREAM_CAPABILITIES = {
    "SafetyGate",
    "TrajectoryStore",
    "RepoMemory",
    "ReplayableBenchmarkHarness",
    "ProtectedVerifier",
    "PatchScorer",
    "PRReporter",
    "local diagnostic queue and worker",
}


def test_failure_vector_support_matrix_contract_is_complete() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "sdetkit.failure_vector.support_matrix.v1"
    assert payload["roadmap_lane"] == "Foundation / FailureVectorEngine"
    assert (
        payload["next_lane_after_completion"]
        == "Cross-provider adoption and real-repository evidence"
    )

    rows = payload["supported_failure_classes"]
    classes = {row["failure_class"] for row in rows}

    assert classes == EXPECTED_CLASSES
    assert set(payload["completed_downstream_capabilities"]) == EXPECTED_DOWNSTREAM_CAPABILITIES
    for row in rows:
        assert row["default_risk"] in {"low", "medium", "high"}
        assert row["review_policy"]
        assert row["first_signal_contract"]
        assert row["artifact_coverage"]


def test_failure_vector_support_matrix_blocks_authority_not_completed_layers() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

    blocked_items = {item["item"] for item in payload["blocked_until_future_wave"]}

    assert blocked_items == {
        "broad automatic patch application",
        "automatic merge authorization",
        "hosted service or cloud infrastructure",
    }
    assert "SafetyGate policy expansion" not in blocked_items
    assert "TrajectoryStore / RepoMemory expansion" not in blocked_items


def test_failure_vector_support_matrix_markdown_matches_contract() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    markdown = DOC_PATH.read_text(encoding="utf-8")

    assert "FailureVector support matrix" in markdown
    assert "docs/contracts/failure-vector-support-matrix.v1.json" in markdown
    assert "Do not repeat completed work" in markdown
    assert "Cross-provider adoption and real-repository evidence" in markdown

    for capability in payload["completed_downstream_capabilities"]:
        assert f"`{capability}`" in markdown
    for row in payload["supported_failure_classes"]:
        assert f"`{row['failure_class']}`" in markdown
