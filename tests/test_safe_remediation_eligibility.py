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
            "context": [{"text": "Fixing tests/test_example.py"}],
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
            "context": [{"text": " --> src/sdetkit/example.py:1:1"}],
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


def test_safe_remediation_blocks_mixed_formatting_and_test_failure() -> None:
    result = eligibility.classify_check_failure(
        name="Full CI lane",
        diagnosis={"code": "PYTEST_ASSERTION_FAILURE"},
        first_failure={
            "line": "FAILED tests/test_behavior.py::test_contract - AssertionError",
            "tool": "pytest",
            "kind": "test_failure",
        },
        log_text="ruff format\n1 file reformatted\n",
    )

    assert result["safe_to_auto_fix"] is False
    assert result["strategy"] == "review_first"
    assert result["category"] == "review_first"
    assert "dominates" in result["reason"]


def test_safe_remediation_blocks_mixed_formatting_and_security_signal() -> None:
    signal = "High " + "entropy string literal detected."
    result = eligibility.classify_check_failure(
        name="security-gate",
        diagnosis={"code": "SEC_HIGH_ENTROPY_STRING"},
        first_failure={
            "line": signal + " src/sdetkit/example.py",
            "tool": "security",
            "kind": "finding",
        },
        log_text="ruff format\n1 file reformatted\n" + signal + "\n",
    )

    assert result["safe_to_auto_fix"] is False
    assert result["strategy"] == "review_first"
    assert result["category"] == "review_first"
    assert "dominates" in result["reason"]


def test_safe_remediation_blocks_formatting_without_affected_files() -> None:
    result = eligibility.classify_check_failure(
        name="autopilot",
        diagnosis={"code": "PRE_COMMIT_FORMAT_DRIFT"},
        first_failure={
            "line": "- files were modified by this hook",
            "tool": "pre_commit",
            "kind": "format_drift",
        },
        log_text="ruff format\n1 file reformatted\n",
    )

    assert result["safe_to_auto_fix"] is False
    assert result["strategy"] == "review_first"
    assert result["affected_files"] == []
    assert "no identified affected files" in result["reason"]


def test_safe_remediation_blocks_formatting_with_unapproved_path_evidence() -> None:
    result = eligibility.classify_check_failure(
        name="autopilot",
        diagnosis={"code": "PRE_COMMIT_FORMAT_DRIFT"},
        first_failure={
            "line": "- files were modified by this hook",
            "tool": "pre_commit",
            "kind": "format_drift",
            "context": [
                {
                    "text": "Fixing home/runner/work/DevS69-sdetkit/DevS69-sdetkit/tools/maintenance_autopilot.py"
                },
                {"text": "Fixing tools/maintenance_autopilot.py"},
            ],
        },
        log_text="ruff format\n1 file reformatted\n",
    )

    assert result["safe_to_auto_fix"] is False
    assert result["strategy"] == "review_first"
    assert "outside approved safe-fix paths" in result["reason"]


def _assert_no_automation_boundary(result: dict) -> None:
    assert result["automation_allowed"] is False
    assert result["auto_fix_allowed_now"] is False
    assert result["patch_application_allowed"] is False
    assert result["merge_authorized"] is False
    assert result["semantic_equivalence_proven"] is False
    assert result["requires_human_review"] is True


def test_safe_remediation_candidate_preserves_no_automation_boundary() -> None:
    result = eligibility.classify_check_failure(
        name="autopilot",
        diagnosis={"code": "PRE_COMMIT_FORMAT_DRIFT"},
        first_failure={
            "line": "- files were modified by this hook",
            "tool": "pre_commit",
            "kind": "format_drift",
            "context": [{"text": "Fixing tests/test_example.py"}],
        },
    )

    assert result["safe_to_auto_fix"] is True
    _assert_no_automation_boundary(result)


def test_safe_remediation_review_first_preserves_no_automation_boundary() -> None:
    result = eligibility.classify_check_failure(
        name="Full CI lane",
        diagnosis={"code": "PYTEST_ASSERTION_FAILURE"},
        first_failure={
            "line": "FAILED tests/test_behavior.py::test_contract - AssertionError",
            "tool": "pytest",
            "kind": "test_failure",
        },
    )

    assert result["safe_to_auto_fix"] is False
    assert result["strategy"] == "review_first"
    _assert_no_automation_boundary(result)
