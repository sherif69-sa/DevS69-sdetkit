from __future__ import annotations

from typing import Any

import pytest

from sdetkit.decision_envelope import build_decision_envelope

REPOSITORY = "sherif69-sa/DevS69-sdetkit"
COMMIT_SHA = "a" * 40


def _safe_gate() -> dict[str, object]:
    return {
        "failure_kind": "formatter_only",
        "ownership_area": "tests/test_widget.py",
        "risk": "low",
        "safe_fix_allowed": True,
        "review_first": False,
        "security_relevance": False,
        "proof_commands": ["python -m ruff format --check tests/test_widget.py"],
    }


@pytest.mark.parametrize(
    "nested_payload",
    [
        {"contract": {"patch_application_allowed": True}},
        {"decision_boundary": {"merge_authorized": "true"}},
        {"evidence": [{"authority": {"publication_authorized": 1}}]},
    ],
)
def test_rejects_authority_expansion_at_any_nested_depth(
    nested_payload: dict[str, Any],
) -> None:
    failure_vector: dict[str, Any] = {
        "failure_class": "formatter_only",
        "actual_failure": "1 file would be reformatted",
        "affected_files": ["tests/test_widget.py"],
        **nested_payload,
    }

    with pytest.raises(ValueError, match="expands authority"):
        build_decision_envelope(
            repository=REPOSITORY,
            commit_sha=COMMIT_SHA,
            failure_vector=failure_vector,
            safety_gate=_safe_gate(),
        )
