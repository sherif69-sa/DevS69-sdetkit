from pathlib import Path

from sdetkit.failure_vector import (
    build_failure_vector_bundle,
    extract_failure_vector,
    render_failure_vector_bundle_report,
    render_failure_vector_report,
    write_failure_vector,
    write_failure_vector_bundle,
)


def test_failure_vector_extracts_first_pytest_failure() -> None:
    log_text = """
    Run PYTHONPATH=src python -m pytest -q
    FAILED tests/test_widget.py::test_widget_contract - AssertionError
    Process completed with exit code 1
    """

    vector = extract_failure_vector(log_text, check="CI / test", environment="github_actions")

    assert vector.schema_version == "sdetkit.failure_vector.v1"
    assert vector.check == "CI / test"
    assert vector.exit_code == 1
    assert vector.failure_class == "test"
    assert vector.risk == "medium"
    assert vector.scope == "pr_owned_only"
    assert vector.safe_fix_candidate is False
    assert vector.first_failing_line == (
        "FAILED tests/test_widget.py::test_widget_contract - AssertionError"
    )
    assert vector.affected_files == ("tests/test_widget.py",)
    assert vector.local_repro_command == (
        "PYTHONPATH=src python -m pytest -q tests/test_widget.py::test_widget_contract -o addopts="
    )


def test_failure_vector_marks_formatter_only_as_safe_candidate() -> None:
    log_text = """
    ruff format..............................................................Failed
    tests/test_widget.py
    1 file would be reformatted
    """

    vector = extract_failure_vector(log_text, check="pre-commit / ruff format")

    assert vector.failure_class == "formatter_only"
    assert vector.risk == "low"
    assert vector.safe_fix_candidate is True
    assert vector.affected_files == ("tests/test_widget.py",)
    assert vector.local_repro_command == ("python -m ruff format --check tests/test_widget.py")


def test_failure_vector_blocks_unknown_failure_review_first() -> None:
    log_text = """
    custom quality wrapper returned an unexpected integrity result
    Process completed with exit code 42
    """

    vector = extract_failure_vector(log_text, check="quality wrapper")

    assert vector.failure_class == "unknown"
    assert vector.risk == "high"
    assert vector.scope == "unknown"
    assert vector.safe_fix_candidate is False
    assert vector.local_repro_command is None


def test_failure_vector_can_write_deterministic_json(tmp_path: Path) -> None:
    vector = extract_failure_vector(
        "FAILED tests/test_widget.py::test_widget_contract - AssertionError",
        check="CI",
    )
    out = tmp_path / "build" / "sdetkit" / "failure-vector.json"

    write_failure_vector(vector, out)

    text = out.read_text(encoding="utf-8")
    assert '"schema_version": "sdetkit.failure_vector.v1"' in text
    assert '"failure_class": "test"' in text


def test_failure_vector_prefers_mypy_error_over_run_command() -> None:
    log_text = """
    Run python -m mypy src
    src/sdetkit/example.py:10: error: Incompatible return value type
    Process completed with exit code 1
    """

    vector = extract_failure_vector(log_text, check="mypy", environment="github_actions")

    assert vector.command == "python -m mypy src"
    assert vector.failure_class == "type"
    assert vector.first_failing_line == (
        "src/sdetkit/example.py:10: error: Incompatible return value type"
    )
    assert vector.affected_files == ("src/sdetkit/example.py",)
    assert vector.local_repro_command == "python -m mypy src"


def test_failure_vector_report_includes_command_scope_and_affected_files() -> None:
    vector = extract_failure_vector(
        "Run python -m mypy src\n"
        "src/sdetkit/example.py:10: error: Incompatible return value type\n",
        check="mypy",
    )

    report = render_failure_vector_report(vector)

    assert "- command: `python -m mypy src`" in report
    assert "- scope: `pr_owned_only`" in report
    assert "- affected_files: `src/sdetkit/example.py`" in report


def test_failure_vector_bundle_summarizes_multiple_logs(tmp_path: Path) -> None:
    test_log = tmp_path / "pytest" / "ci.log"
    lint_log = tmp_path / "lint" / "ci.log"
    test_log.parent.mkdir()
    lint_log.parent.mkdir()

    test_log.write_text(
        "Run python -m pytest -q\n"
        "FAILED tests/test_widget.py::test_widget_contract - AssertionError\n"
        "Process completed with exit code 1\n",
        encoding="utf-8",
    )
    lint_log.write_text(
        "Run python -m ruff format --check .\n"
        "ruff format..............................................................Failed\n"
        "tests/test_widget.py\n"
        "1 file would be reformatted\n",
        encoding="utf-8",
    )

    payload = build_failure_vector_bundle(
        [test_log, lint_log],
        environment="github_actions",
    )

    assert payload["schema_version"] == "sdetkit.failure_vector.bundle.v1"
    assert payload["failure_vector_count"] == 2
    assert payload["summary"]["by_failure_class"] == {
        "formatter_only": 1,
        "test": 1,
    }
    assert payload["summary"]["safe_fix_candidate_count"] == 1
    assert payload["summary"]["review_first_count"] == 1

    report = render_failure_vector_bundle_report(payload)
    assert "# Failure Vector Bundle" in report
    assert "- `formatter_only`: `1`" in report
    assert "- `test`: `1`" in report


def test_failure_vector_bundle_can_write_deterministic_json(tmp_path: Path) -> None:
    log = tmp_path / "pytest" / "ci.log"
    out = tmp_path / "build" / "sdetkit" / "failure-vectors.json"
    log.parent.mkdir()
    log.write_text(
        "FAILED tests/test_widget.py::test_widget_contract - AssertionError\n",
        encoding="utf-8",
    )

    payload = write_failure_vector_bundle([log], out, environment="local")

    assert payload["failure_vector_count"] == 1
    text = out.read_text(encoding="utf-8")
    assert '"schema_version": "sdetkit.failure_vector.bundle.v1"' in text
    assert '"failure_class": "test"' in text
