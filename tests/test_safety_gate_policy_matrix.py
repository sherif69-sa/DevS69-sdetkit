from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sdetkit.safety_gate import (
    GENERAL_BLOCKED_ACTIONS,
    SAFE_FIX_CLASSES,
    evaluate_failure_vector,
)

POLICY_PATH = Path("docs/contracts/safety-gate-policy-matrix.v1.json")
FAILURE_VECTOR_MATRIX_PATH = Path("docs/contracts/failure-vector-support-matrix.v1.json")
DOC_PATH = Path("docs/safety-gate-policy-matrix.md")


@dataclass(frozen=True)
class MinimalFailureVector:
    failure_class: str
    risk: str = "low"
    scope: str = "pr_owned_only"
    safe_fix_candidate: bool = True
    affected_files: tuple[str, ...] = ("tests/test_widget.py",)
    local_repro_command: str | None = "python -m ruff format --check tests/test_widget.py"


def _load_policy() -> dict[str, object]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def test_safety_gate_policy_matrix_matches_failure_vector_support_matrix() -> None:
    policy = _load_policy()
    failure_vector_matrix = json.loads(FAILURE_VECTOR_MATRIX_PATH.read_text(encoding="utf-8"))

    policy_classes = {row["failure_class"] for row in policy["policy_by_failure_class"]}
    supported_classes = {
        row["failure_class"] for row in failure_vector_matrix["supported_failure_classes"]
    }

    assert policy["schema_version"] == "sdetkit.safety_gate.policy_matrix.v1"
    assert policy["roadmap_lane"] == "Wave B / SafetyGate policy expansion"
    assert policy_classes == supported_classes


def test_safety_gate_policy_matrix_matches_current_safe_fix_classes() -> None:
    policy = _load_policy()

    safe_fix_classes = set(policy["safe_fix_allowed_only_when"]["failure_class_in"])
    assert safe_fix_classes == set(SAFE_FIX_CLASSES)
    assert policy["safe_fix_allowed_only_when"]["local_repro_command"] == "non_empty"

    allowed_rows = {
        row["failure_class"]
        for row in policy["policy_by_failure_class"]
        if row["default_decision"] == "safe_fix_allowed_if_all_global_conditions_pass"
    }
    assert allowed_rows == set(SAFE_FIX_CLASSES)

    review_first_rows = {
        row["failure_class"]
        for row in policy["policy_by_failure_class"]
        if row["default_decision"] == "review_first"
    }
    assert review_first_rows.isdisjoint(allowed_rows)


def test_safety_gate_policy_matrix_matches_runtime_decisions() -> None:
    policy = _load_policy()
    rows = {
        row["failure_class"]: row["default_decision"] for row in policy["policy_by_failure_class"]
    }

    for failure_class, default_decision in rows.items():
        decision = evaluate_failure_vector(MinimalFailureVector(failure_class))

        if default_decision == "safe_fix_allowed_if_all_global_conditions_pass":
            assert decision.safe_fix_allowed is True
            assert decision.review_first is False
            assert decision.allowed_files == ("tests/test_widget.py",)
        else:
            assert decision.safe_fix_allowed is False
            assert decision.review_first is True
            assert decision.allowed_files == ()


def test_safety_gate_policy_matrix_keeps_global_blocked_actions_aligned() -> None:
    policy = _load_policy()

    assert tuple(policy["global_blocked_actions"]) == GENERAL_BLOCKED_ACTIONS

    blocked_items = {item["item"] for item in policy["blocked_until_future_wave"]}
    assert "automatic patch application" in blocked_items
    assert "merge authorization" in blocked_items
    assert "TrajectoryStore / RepoMemory expansion" in blocked_items
    assert "cloud, service, dashboard, or worker orchestration" in blocked_items


def test_safety_gate_policy_matrix_markdown_matches_contract() -> None:
    policy = _load_policy()
    markdown = DOC_PATH.read_text(encoding="utf-8")

    assert "SafetyGate policy matrix" in markdown
    assert "docs/contracts/safety-gate-policy-matrix.v1.json" in markdown
    assert "automatic patch application" in markdown
    assert "local repro command" in markdown
    assert "merge authorization" in markdown

    for row in policy["policy_by_failure_class"]:
        assert f"`{row['failure_class']}`" in markdown
