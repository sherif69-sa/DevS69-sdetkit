from pathlib import Path

from sdetkit.failure_vector import extract_failure_vector, write_failure_vector


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
