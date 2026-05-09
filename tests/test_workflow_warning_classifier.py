from __future__ import annotations

from sdetkit import workflow_warning_classifier

SETUP_PYTHON_FALLBACK_WARNING = """
Run actions/setup-python@v6
Warning: Neither 'python-version' nor 'python-version-file' inputs were supplied.
Warning: .python-version doesn't exist.
Warning: The `python-version` input is not set. The version of Python currently in `PATH` will be used.
"""


def _codes(text: str) -> set[str]:
    return {item.code for item in workflow_warning_classifier.classify_warning_text(text)}


def test_setup_python_path_fallback_warning_is_classified() -> None:
    warnings = workflow_warning_classifier.classify_warning_text(SETUP_PYTHON_FALLBACK_WARNING)

    assert len(warnings) == 1
    warning = warnings[0]
    assert warning.code == "SETUP_PYTHON_PATH_FALLBACK"
    assert warning.severity == "low"
    assert warning.confidence == "high"
    assert "PATH" in warning.summary
    assert "tests/test_github_setup_python_pinning.py" in warning.proof_command


def test_warning_payload_for_setup_python_fallback_is_monitor() -> None:
    payload = workflow_warning_classifier.classify_warning_payload(SETUP_PYTHON_FALLBACK_WARNING)

    assert payload["ok"] is True
    assert payload["status"] == "monitor"
    assert payload["warning_count"] == 1
    warnings = payload["warnings"]
    assert isinstance(warnings, list)
    assert warnings[0]["code"] == "SETUP_PYTHON_PATH_FALLBACK"


def test_projects_classic_deprecation_warning_is_classified() -> None:
    text = """
    GraphQL: Projects (classic) is being deprecated in favor of the new Projects experience.
    repository.pullRequest.projectCards
    """

    assert "GH_PROJECTS_CLASSIC_DEPRECATION" in _codes(text)


def test_high_entropy_test_literal_warning_is_classified() -> None:
    text = """
    github-advanced-security
    Warning
    sdetkit-security-gate / High entropy string literal detected.
    tests/test_example.py
    """

    assert "SYNTHETIC_LITERAL_SCANNER_NOISE" in _codes(text)


def test_unpinned_setup_python_warning_is_classified_as_needs_attention() -> None:
    text = "actions/setup-python appears not pinned in a workflow template"

    payload = workflow_warning_classifier.classify_warning_payload(text)

    assert payload["status"] == "needs_attention"
    assert "SETUP_PYTHON_ACTION_UNPINNED" in _codes(text)


def test_empty_warning_text_is_clear() -> None:
    payload = workflow_warning_classifier.classify_warning_payload("")

    assert payload["status"] == "clear"
    assert payload["warning_count"] == 0
    assert workflow_warning_classifier.render_warning_summary("") == ("Workflow warnings: none")


def test_render_warning_summary_is_operator_readable() -> None:
    summary = workflow_warning_classifier.render_warning_summary(SETUP_PYTHON_FALLBACK_WARNING)

    assert "Workflow warnings:" in summary
    assert "SETUP_PYTHON_PATH_FALLBACK" in summary
    assert "setup-python is falling back to runner PATH" in summary


def test_setup_python_fallback_does_not_double_count_unpinned_warning() -> None:
    codes = _codes(SETUP_PYTHON_FALLBACK_WARNING)

    assert codes == {"SETUP_PYTHON_PATH_FALLBACK"}


def test_multiple_warning_families_can_be_reported_together() -> None:
    text = (
        SETUP_PYTHON_FALLBACK_WARNING
        + "\n"
        + "github-advanced-security High entropy string literal detected in tests/test_file.py"
    )

    codes = _codes(text)

    assert "SETUP_PYTHON_PATH_FALLBACK" in codes
    assert "SYNTHETIC_LITERAL_SCANNER_NOISE" in codes


def test_warning_status_ranks_medium_above_low() -> None:
    warnings = workflow_warning_classifier.classify_warning_text(
        "actions/setup-python appears not pinned in a workflow template"
    )

    assert workflow_warning_classifier.warning_status(warnings) == "needs_attention"
