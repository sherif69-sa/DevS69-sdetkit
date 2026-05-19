from __future__ import annotations

from sdetkit import safe_remediation_eligibility as eligibility


def test_safe_remediation_allows_format_hook_modified_files() -> None:
    result = eligibility.classify_check_failure(
        name="autopilot",
        diagnosis={"code": "PRE_COMMIT_FORMAT_DRIFT"},
        first_failure={
            "line": "- files were modified by this hook",
            "tool": "pre_commit",
            "kind": "format_drift",
        },
    )

    assert result["schema_version"] == "sdetkit.safe_remediation_eligibility.v1"
    assert result["safe_to_auto_fix"] is True
    assert result["strategy"] == "run_pre_commit"
    assert result["category"] == "formatting_only"
    assert "python -m pre_commit run -a" in result["proof_commands"]


def test_safe_remediation_allows_ruff_import_sorting_only() -> None:
    result = eligibility.classify_check_failure(
        name="Fast CI lane (py3.12)",
        diagnosis={"code": "RUFF_IMPORT_SORT"},
        first_failure={
            "line": "I001 [*] Import block is un-sorted or un-formatted",
            "tool": "ruff",
            "kind": "format_drift",
        },
    )

    assert result["safe_to_auto_fix"] is True
    assert result["strategy"] == "run_pre_commit"


def test_safe_remediation_blocks_type_runtime_release_and_security_failures() -> None:
    unsafe_lines = [
        "src/sdetkit/example.py:10: error: Incompatible return value type",
        "Traceback (most recent call last):",
        "ERROR: InvalidDistribution: Metadata is invalid",
        "High-entropy string literal detected.",
    ]

    for line in unsafe_lines:
        result = eligibility.classify_check_failure(
            name="ci",
            diagnosis={"code": "UNKNOWN"},
            first_failure={"line": line, "tool": "unknown", "kind": "error"},
        )

        assert result["safe_to_auto_fix"] is False
        assert result["strategy"] == "review_first"


def test_safe_remediation_extracts_affected_files_from_log_context() -> None:
    result = eligibility.classify_check_failure(
        name="autopilot",
        diagnosis={"code": "PRE_COMMIT_FORMAT_DRIFT"},
        first_failure={
            "line": "- files were modified by this hook",
            "tool": "pre_commit",
            "kind": "format_drift",
            "context": [
                {"line_number": 1, "text": "fix end of files................Failed"},
                {"line_number": 2, "text": "Fixing tests/test_example.py"},
            ],
        },
        log_text="ruff format\n1 file reformatted\n",
    )

    assert result["safe_to_auto_fix"] is True
    assert result["strategy"] == "run_pre_commit"
    assert result["affected_files"] == ["tests/test_example.py"]
