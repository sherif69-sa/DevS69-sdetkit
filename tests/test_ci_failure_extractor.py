from __future__ import annotations

import json
from pathlib import Path

from sdetkit.ci_failure_extractor import build_failed_check_logs, main
from sdetkit.diagnostic_vector_engine import build_diagnostic_vector


def test_ci_failure_extractor_turns_pytest_log_into_failure_vector() -> None:
    log_path = Path("tests/fixtures/ci_failures/pytest_assertion/ci_log.txt")

    payload = build_failed_check_logs([log_path])

    assert payload["schema_version"] == "sdetkit.ci_failure_extractor.v1"
    assert payload["failed_check_count"] == 1
    record = payload["failed_checks"][0]
    assert record["first_failure_line"].startswith(
        "FAILED tests/test_widget.py::test_widget_contract"
    )
    assert record["failure_class"] == "test"
    assert record["affected_files"] == ["tests/test_widget.py"]

    vector_payload = build_diagnostic_vector(failed_check_logs=payload)
    vector = vector_payload["failure_vectors"][0]
    assert vector["failure_class"] == "test"
    assert vector["failing_file"] == "tests/test_widget.py"
    assert vector["failing_test"] == "tests/test_widget.py::test_widget_contract"


def test_ci_failure_extractor_marks_formatter_only_as_safe_candidate(tmp_path: Path) -> None:
    log_path = tmp_path / "format-log.txt"
    log_path.write_text(
        "Run python -m pre_commit run -a\n"
        "ruff format..............................Failed\n"
        "1 file would be reformatted\n"
        "Error: Process completed with exit code 1.\n",
        encoding="utf-8",
    )

    payload = build_failed_check_logs([log_path])
    record = payload["failed_checks"][0]

    assert record["failure_class"] == "formatter_only"
    assert record["safe_to_auto_fix"] is True
    assert record["review_first"] is False

    vector_payload = build_diagnostic_vector(failed_check_logs=payload)
    vector = vector_payload["failure_vectors"][0]
    assert vector["safe_fix_candidate"] is True
    assert vector["failure_class"] == "formatter_only"


def test_ci_failure_extractor_marks_mypy_as_review_first(tmp_path: Path) -> None:
    log_path = tmp_path / "mypy-log.txt"
    log_path.write_text(
        "Run python -m mypy src\n"
        "src/sdetkit/example.py:10: error: Incompatible return value type\n"
        "Error: Process completed with exit code 1.\n",
        encoding="utf-8",
    )

    payload = build_failed_check_logs([log_path])
    record = payload["failed_checks"][0]

    assert record["failure_class"] == "type"
    assert record["review_first"] is True
    assert record["affected_files"] == ["src/sdetkit/example.py"]

    vector_payload = build_diagnostic_vector(failed_check_logs=payload)
    vector = vector_payload["failure_vectors"][0]
    assert vector["review_first"] is True
    assert vector["risk_surface"] == "type_contract"


def test_ci_failure_extractor_cli_writes_failed_check_logs(tmp_path: Path, capsys) -> None:
    log_path = tmp_path / "unknown-log.txt"
    out = tmp_path / "failed-check-logs.json"
    log_path.write_text("Error: Process completed with exit code 1.\n", encoding="utf-8")

    rc = main(["--log", str(log_path), "--out", str(out), "--format", "text"])

    assert rc == 0
    stdout = capsys.readouterr().out
    assert "failed_check_logs_json=" in stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["summary"]["unknown_count"] == 1
    assert payload["failed_checks"][0]["review_first"] is True
