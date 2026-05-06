from __future__ import annotations

import json

from sdetkit.pr_investigation_summary import (
    build_pr_investigation_summary,
    render_pr_investigation_summary_markdown,
    write_pr_investigation_summary,
)


def test_pr_investigation_summary_uses_adaptive_diagnosis_and_policy():
    payload = build_pr_investigation_summary(
        log_text=(
            "AttributeError: SdetAsyncHttpClient object has no attribute "
            "get_json_list_paginated_envelope async parity"
        ),
        surface="netclient",
        memory_seen_count=3,
        memory_fixed_count=2,
    )

    assert payload["schema_version"] == "sdetkit.pr_investigation_summary.v1"
    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["classification"] == "MISSING_PUBLIC_API_PARITY"
    assert payload["confidence"] == "high"
    assert payload["safe_fix_status"] == "review required"
    assert payload["auto_fix_allowed_now"] is False
    assert payload["requires_human_review"] is True
    assert payload["surface"] == "netclient"
    assert payload["memory"] == {"seen_count": 3, "manual_fix_count": 2}
    assert payload["safe_fix_policy"]["route"] == "review_first_product_fix"
    assert payload["diagnosis"]["diagnoses"][0]["code"] == "MISSING_PUBLIC_API_PARITY"
    assert "pytest" in payload["next_command"]


def test_pr_investigation_summary_marks_mechanical_class_candidate_later():
    payload = build_pr_investigation_summary(
        log_text="ruff format failed: 2 files reformatted and files were modified by this hook",
        surface="tests",
    )

    assert payload["classification"] == "PRE_COMMIT_FORMAT_DRIFT"
    assert payload["safe_fix_status"] == "candidate later"
    assert payload["safe_fix_policy"]["route"] == "safe_mechanical_candidate_later"
    assert payload["safe_fix_policy"]["auto_fix_allowed_now"] is False
    assert payload["automation_allowed"] is False


def test_pr_investigation_summary_markdown_is_comment_ready():
    payload = build_pr_investigation_summary(
        log_text="Exit: Missing test dependencies: hypothesis, yaml.",
        surface="dependencies",
        memory_seen_count=1,
        memory_fixed_count=0,
    )

    rendered = render_pr_investigation_summary_markdown(payload)

    assert rendered.startswith("### Failure investigation")
    assert "classification: **MISSING_TEST_DEPENDENCY**" in rendered
    assert "safe-fix status: **review required**" in rendered
    assert "automation allowed: **False**" in rendered
    assert "memory: seen 1 time(s), fixed manually 0 time(s)" in rendered
    assert "surface: **dependencies**" in rendered
    assert "#### Proof commands" in rendered


def test_pr_investigation_summary_blank_log_falls_back_to_review_required():
    payload = build_pr_investigation_summary(log_text="", memory_seen_count=-3, memory_fixed_count=-1)

    assert payload["classification"] == "UNKNOWN_REVIEW_REQUIRED"
    assert payload["confidence"] == "medium"
    assert payload["safe_fix_status"] == "review required"
    assert payload["memory"] == {"seen_count": 0, "manual_fix_count": 0}
    assert payload["next_command"] == "python -m sdetkit investigate failure --log <log> --format markdown"


def test_write_pr_investigation_summary_json_and_markdown(tmp_path):
    payload = build_pr_investigation_summary(
        log_text="TypeError: Resp() takes no arguments because test double defines init_ instead of __init__",
        surface="netclient",
    )
    json_out = tmp_path / "summary.json"
    markdown_out = tmp_path / "summary.md"

    assert write_pr_investigation_summary(payload, json_out) == json_out
    assert write_pr_investigation_summary(payload, markdown_out) == markdown_out

    written_json = json.loads(json_out.read_text(encoding="utf-8"))
    written_markdown = markdown_out.read_text(encoding="utf-8")
    assert written_json["classification"] == "BROKEN_TEST_DOUBLE"
    assert written_json["safe_fix_policy"]["route"] == "review_first_test_fix"
    assert "classification: **BROKEN_TEST_DOUBLE**" in written_markdown
    assert "surface: **netclient**" in written_markdown
