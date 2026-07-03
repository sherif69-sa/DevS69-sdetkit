from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from html import escape
from typing import Any

from . import _pr_quality_live_dashboard_core as _core
from .pr_quality_adaptive_diagnosis import attach_adaptive_diagnosis

JsonObject = dict[str, Any]
AUTHORITY_FIELDS = (
    "reporting_only",
    "automation_allowed",
    "patch_application_allowed",
    "security_dismissal_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)


def _as_dict(value: object) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    rendered = str(value).strip()
    return rendered or default


def _markdown_code(value: object, default: str = "") -> str:
    return _text(value, default).replace("`", "'").replace("\n", " ")


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
        if metric and expected is not None and actual is not None:
            return (
                f"{metric} = {_display_failure_literal(expected)}",
                f"{metric} = {_display_failure_literal(actual)}",
            )
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


def _adaptive_diagnosis_card(value: JsonObject) -> JsonObject:
    card = _as_dict(value.get("adaptive_diagnosis"))
    if card:
        return card
    return _as_dict(_as_dict(value.get("primary_failure")).get("adaptive_diagnosis"))


def _adaptive_diagnosis_markdown(snapshot: JsonObject) -> str:
    card = _adaptive_diagnosis_card(snapshot)
    if not card:
        return ""

    checks = _as_dict(card.get("checks"))
    lines = [
        "## Adaptive Diagnosis",
        "",
        "| Signal | Value |",
        "|---|---|",
        (
            "| Completeness | "
            f"`{_markdown_code(card.get('diagnostic_completeness'), 'insufficient')}` |"
        ),
        f"| Confidence | `{_markdown_code(card.get('confidence'), 'low')}` |",
        f"| Failure class | `{_markdown_code(card.get('failure_class'), 'unknown')}` |",
        (
            "| Review first | "
            f"`{'true' if bool(card.get('review_first', True)) else 'false'}` |"
        ),
        "",
        "### Safeguards",
        "",
    ]
    if checks:
        lines.extend(
            f"- `{_markdown_code(name)}`: "
            f"`{'pass' if bool(passed) else 'missing'}`"
            for name, passed in sorted(checks.items(), key=lambda item: _text(item[0]))
        )
    else:
        lines.append("- No adaptive checks were emitted.")

    for title, key, empty in (
        ("Owner files", "owner_files", "No owner file was resolved."),
        ("Focused proof", "proof_commands", "No focused proof command was resolved."),
        ("Evidence gaps", "evidence_gaps", "No evidence gaps were reported."),
    ):
        lines.extend(("", f"### {title}", ""))
        values = [_text(item) for item in _as_list(card.get(key)) if _text(item)]
        lines.extend(f"- `{_markdown_code(item)}`" for item in values)
        if not values:
            lines.append(f"- {empty}")

    lines.extend(
        (
            "",
            "### Next human action",
            "",
            _text(
                card.get("next_human_action"),
                "Collect exact failure evidence before changing code.",
            ),
            "",
            "### Authority boundary",
            "",
        )
    )
    lines.extend(
        f"- `{field}={'true' if bool(card.get(field, False)) else 'false'}`"
        for field in AUTHORITY_FIELDS
    )
    lines.append("")
    return "\n".join(lines)


def _html_list(values: object, *, empty: str) -> str:
    items = [_text(item) for item in _as_list(values) if _text(item)]
    if not items:
        return f"<p>{escape(empty)}</p>"
    return "<ul>" + "".join(f"<li><code>{escape(item)}</code></li>" for item in items) + "</ul>"


def _adaptive_diagnosis_html(snapshot: JsonObject) -> str:
    card = _adaptive_diagnosis_card(snapshot)
    if not card:
        return ""

    checks = _as_dict(card.get("checks"))
    check_rows = "".join(
        "<tr>"
        f"<td><code>{escape(_text(name))}</code></td>"
        f"<td>{'Pass' if bool(passed) else 'Missing'}</td>"
        "</tr>"
        for name, passed in sorted(checks.items(), key=lambda item: _text(item[0]))
    )
    if not check_rows:
        check_rows = '<tr><td colspan="2">No adaptive checks were emitted.</td></tr>'

    authority_rows = "".join(
        "<tr>"
        f"<td><code>{field}</code></td>"
        f"<td>{'true' if bool(card.get(field, False)) else 'false'}</td>"
        "</tr>"
        for field in AUTHORITY_FIELDS
    )
    completeness = escape(_text(card.get("diagnostic_completeness"), "insufficient").title())
    confidence = escape(_text(card.get("confidence"), "low").title())
    failure_class = escape(
        _text(card.get("failure_class"), "unknown").replace("_", " ").title()
    )
    review_first = "Yes" if bool(card.get("review_first", True)) else "No"
    next_action = escape(
        _text(
            card.get("next_human_action"),
            "Collect exact failure evidence before changing code.",
        )
    )

    return "".join(
        (
            '<section id="adaptive-diagnosis" class="section adaptive-diagnosis">',
            '<div class="section-heading"><div>',
            '<div class="eyebrow">Contributor evidence</div>',
            "<h2>Adaptive Diagnosis</h2>",
            "</div><p>The first violated contract, evidence quality, and review-first action.</p>",
            "</div>",
            '<div class="review-grid">',
            f'<article class="review-panel"><span>Completeness</span><h3>{completeness}</h3></article>',
            f'<article class="review-panel"><span>Confidence</span><h3>{confidence}</h3></article>',
            f'<article class="review-panel"><span>Failure class</span><h3>{failure_class}</h3></article>',
            f'<article class="review-panel"><span>Review first</span><h3>{review_first}</h3></article>',
            "</div>",
            "<h3>Safeguards</h3>",
            "<table><thead><tr><th>Check</th><th>Result</th></tr></thead>",
            f"<tbody>{check_rows}</tbody></table>",
            "<h3>Owner files</h3>",
            _html_list(card.get("owner_files"), empty="No owner file was resolved."),
            "<h3>Focused proof</h3>",
            _html_list(
                card.get("proof_commands"),
                empty="No focused proof command was resolved.",
            ),
            "<h3>Evidence gaps</h3>",
            _html_list(card.get("evidence_gaps"), empty="No evidence gaps were reported."),
            "<h3>Next human action</h3>",
            f"<p><strong>{next_action}</strong></p>",
            "<h3>Authority boundary</h3>",
            "<table><thead><tr><th>Field</th><th>Value</th></tr></thead>",
            f"<tbody>{authority_rows}</tbody></table>",
            "</section>",
        )
    )


def _inject_adaptive_html(rendered: str, snapshot: JsonObject) -> str:
    section = _adaptive_diagnosis_html(snapshot)
    if not rendered or not section:
        return rendered
    for marker in ("</main>", "</body>"):
        if marker in rendered:
            return rendered.replace(marker, section + marker, 1)
    return rendered + section


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
    attach_adaptive_diagnosis(review_model)
    snapshot = _core.build_live_evidence_snapshot(
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
    card = _adaptive_diagnosis_card(review_model)
    if card:
        snapshot["adaptive_diagnosis"] = dict(card)
    return snapshot


def render_live_evidence_markdown(snapshot: JsonObject) -> str:
    rendered = _core.render_live_evidence_markdown(snapshot)
    section = _adaptive_diagnosis_markdown(snapshot)
    if not rendered:
        return section
    if not section:
        return rendered
    return rendered.rstrip() + "\n\n" + section


def render_live_evidence_html(snapshot: JsonObject) -> str:
    return _inject_adaptive_html(_core.render_live_evidence_html(snapshot), snapshot)


def render_live_product_dashboard(
    model: JsonObject,
    *,
    embedded_artifacts: JsonObject | None = None,
) -> str:
    rendered = _core.render_live_product_dashboard(
        model,
        embedded_artifacts=embedded_artifacts,
    )
    return _inject_adaptive_html(rendered, _as_dict(model.get("live_evidence")))
