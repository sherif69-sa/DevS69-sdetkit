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
