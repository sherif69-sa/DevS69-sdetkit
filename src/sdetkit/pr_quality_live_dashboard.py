from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from typing import Any

from . import _pr_quality_live_dashboard_core as _core

JsonObject = dict[str, Any]


def _as_dict(value: object) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    rendered = str(value).strip()
    return rendered or default


def _display_failure_literal(value: object) -> str:
    rendered = _text(value)
    if len(rendered) >= 2 and rendered[0] == rendered[-1] and rendered[0] in {'"', "'"}:
        return rendered[1:-1]
    return rendered


def _structured_expected_observed(message: str) -> tuple[str, str]:
    try:
        payload = ast.literal_eval(message)
    except (SyntaxError, ValueError):
        return "", ""

    rows = payload if isinstance(payload, list) else [payload]
    for row in rows:
        if not isinstance(row, dict):
            continue
        metric = _text(row.get("metric"))
        actual = row.get("actual", row.get("observed"))
        maximum = row.get("maximum")
        expected = row.get("expected")
        if metric and maximum is not None and actual is not None:
            return f"{metric} <= {maximum}", f"{metric} = {actual}"
        if expected is not None and actual is not None:
            return _display_failure_literal(expected), _display_failure_literal(actual)
    return "", ""


def _explicit_expected_observed(message: str) -> tuple[str, str]:
    match = re.search(
        r"\bexpected=(?P<expected>'[^']*'|\"[^\"]*\"|[^;]+);"
        r"\s*observed=(?P<observed>'[^']*'|\"[^\"]*\"|[^;]+)",
        message,
    )
    if match is None:
        return "", ""
    return (
        _display_failure_literal(match.group("expected")),
        _display_failure_literal(match.group("observed")),
    )


def _failure_family_score(value: object) -> tuple[int, int, int]:
    family = _as_dict(value)
    code = _text(family.get("failure_code"))
    return (
        1 if _text(family.get("test_node")) else 0,
        1 if _text(family.get("message")) else 0,
        1 if code and code not in {"UNKNOWN_REVIEW_REQUIRED", "RELEASE_ARTIFACT_INVALID"} else 0,
    )


def _enrich_primary_failure(review_model: JsonObject) -> None:
    primary_failure = _as_dict(review_model.get("primary_failure"))
    if not primary_failure or not bool(primary_failure.get("available", False)):
        return

    families = [
        _as_dict(item)
        for item in _as_list(
            primary_failure.get("families") or review_model.get("failure_families")
        )
        if _as_dict(item)
    ]
    detail = max(families, key=_failure_family_score) if families else {}

    message = _text(primary_failure.get("message") or detail.get("message"))
    test_node = _text(primary_failure.get("test_node") or detail.get("test_node"))
    expected = _text(primary_failure.get("expected"))
    observed = _text(primary_failure.get("observed"))

    if not expected or not observed:
        derived = _explicit_expected_observed(message)
        if not all(derived):
            derived = _structured_expected_observed(message)
        if all(derived):
            expected, observed = derived

    if not expected:
        expected = "check completes successfully"
    if not observed:
        observed = message or (
            f"{_text(primary_failure.get('check_name'), 'check')} reported failure "
            "without detailed output"
        )

    primary_failure["expected"] = expected
    primary_failure["observed"] = observed
    if message and not _text(primary_failure.get("message")):
        primary_failure["message"] = message
    if test_node and not _text(primary_failure.get("test_node")):
        primary_failure["test_node"] = test_node


def build_live_evidence_snapshot(
    *,
    pr_number: int,
    head_sha: str,
    base_sha: str,
    review_model: JsonObject,
    check_intelligence: JsonObject,
    runtime_proof_artifacts: JsonObject,
    artifact_manifest: JsonObject,
    environment: Mapping[str, str] | None = None,
    generated_at: str | None = None,
) -> JsonObject:
    _enrich_primary_failure(review_model)
    return _core.build_live_evidence_snapshot(
        pr_number=pr_number,
        head_sha=head_sha,
        base_sha=base_sha,
        review_model=review_model,
        check_intelligence=check_intelligence,
        runtime_proof_artifacts=runtime_proof_artifacts,
        artifact_manifest=artifact_manifest,
        environment=environment,
        generated_at=generated_at,
    )


render_live_evidence_markdown = _core.render_live_evidence_markdown
render_live_evidence_html = _core.render_live_evidence_html
render_live_product_dashboard = _core.render_live_product_dashboard
