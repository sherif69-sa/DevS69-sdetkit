from sdetkit.failure_vector import extract_failure_vector, render_failure_vector_report


def test_pr_quality_failure_vector_report_renders_review_first_decision() -> None:
    vector = extract_failure_vector(
        """
        custom wrapper failed with unknown output
        Process completed with exit code 42
        """,
        check="PR Quality Comment",
    )

    report = render_failure_vector_report(vector)

    assert "# Failure Vector" in report
    assert "- check: `PR Quality Comment`" in report
    assert "- class: `unknown`" in report
    assert "- risk: `high`" in report
    assert "- safe_fix_candidate: `no`" in report
    assert "- local_repro_command: `none`" in report
    assert "## SafetyGate Decision" in report
    assert "- safe_fix_allowed: `no`" in report
    assert "- review_first: `yes`" in report
    assert "failure_class 'unknown'" in report
    assert "- automation_allowed: `false`" in report


def test_pr_quality_failure_vector_report_renders_exact_pytest_repro() -> None:
    vector = extract_failure_vector(
        "FAILED tests/test_widget.py::test_widget_contract - AssertionError",
        check="CI",
    )

    report = render_failure_vector_report(vector)

    assert "- class: `test`" in report
    assert (
        "- local_repro_command: "
        "`PYTHONPATH=src python -m pytest -q "
        "tests/test_widget.py::test_widget_contract -o addopts=`" in report
    )


def test_pr_quality_failure_vector_report_surfaces_safety_gate_safe_candidate() -> None:
    vector = extract_failure_vector(
        """
        ruff format..............................................................Failed
        tests/test_widget.py
        1 file would be reformatted
        """,
        check="pre-commit / ruff format",
    )

    report = render_failure_vector_report(vector)

    assert "- class: `formatter_only`" in report
    assert "- safe_fix_candidate: `yes`" in report
    assert "## SafetyGate Decision" in report
    assert "- safe_fix_allowed: `yes`" in report
    assert "- review_first: `no`" in report
    assert "- allowed_files: `tests/test_widget.py`" in report
    assert (
        "- proof_commands: `python -m ruff format --check tests/test_widget.py, make proof-after-format`"
        in report
    )
    assert "- patch_application_allowed: `false`" in report
    assert "- merge_authorized: `false`" in report
