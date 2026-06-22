from __future__ import annotations

import json
from pathlib import Path

DECISION = Path("docs/ci/workflow-permission-decisions/pr-quality-trusted-publisher.md")


def _snake(*parts: str) -> str:
    return "_".join(parts)


def _kv(key: str, value: str) -> str:
    return f"{key}={value}"


def _workflow_path(stem: str) -> str:
    return f".github/workflows/{stem}.yml"


def test_pr_quality_publisher_permission_decision_is_scoped_and_human_reviewed() -> None:
    text = DECISION.read_text(encoding="utf-8")
    assert _kv("reviewer", "sherif69-sa") in text
    assert _kv("decision", _snake("approved", "scoped", "permission", "move")) in text
    assert _kv(_snake("source", "workflow"), _workflow_path("pr-quality-comment")) in text
    assert (
        _kv(
            _snake("publisher", "workflow"),
            _workflow_path("pr-quality-publisher"),
        )
        in text
    )
    expected_scopes = json.dumps(["issues: write", "pull-requests: write"])
    assert _kv(_snake("publisher", "write", "scopes"), expected_scopes) in text
    assert _kv(_snake("publisher", "checkout", "allowed"), "false") in text
    assert (
        _kv(
            _snake("publisher", "repository", "code", "execution", "allowed"),
            "false",
        )
        in text
    )
    assert _kv(_snake("remaining", "group", "workflows", "pending"), "true") in text
