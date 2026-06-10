from __future__ import annotations

import json
from pathlib import Path

from sdetkit.ci_failure_extractor import (
    build_failed_check_logs,
    main,
    write_failure_vector_artifacts,
)
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


def test_ci_failure_extractor_writes_failure_vector_artifacts(tmp_path: Path) -> None:
    log_path = tmp_path / "pytest" / "ci.log"
    vectors_out = tmp_path / "failure-vectors.json"
    vectors_md = tmp_path / "failure-vectors.md"
    log_path.parent.mkdir()
    log_path.write_text(
        "Run python -m pytest -q\n"
        "FAILED tests/test_widget.py::test_widget_contract - AssertionError\n"
        "Error: Process completed with exit code 1.\n",
        encoding="utf-8",
    )

    payload = write_failure_vector_artifacts(
        [log_path],
        json_out=vectors_out,
        markdown_out=vectors_md,
        environment="github_actions",
    )

    assert payload["schema_version"] == "sdetkit.failure_vector.bundle.v1"
    assert payload["failure_vector_count"] == 1
    assert vectors_out.exists()
    assert vectors_md.exists()
    assert "# Failure Vector Bundle" in vectors_md.read_text(encoding="utf-8")


def test_ci_failure_extractor_cli_can_emit_failure_vector_bundle(
    tmp_path: Path,
    capsys,
) -> None:
    log_path = tmp_path / "mypy" / "ci.log"
    failed_logs = tmp_path / "failed-check-logs.json"
    vectors_out = tmp_path / "failure-vectors.json"
    vectors_md = tmp_path / "failure-vectors.md"
    log_path.parent.mkdir()
    log_path.write_text(
        "Run python -m mypy src\n"
        "src/sdetkit/example.py:10: error: Incompatible return value type\n"
        "Error: Process completed with exit code 1.\n",
        encoding="utf-8",
    )

    rc = main(
        [
            "--log",
            str(log_path),
            "--out",
            str(failed_logs),
            "--failure-vectors-out",
            str(vectors_out),
            "--failure-vectors-md",
            str(vectors_md),
            "--environment",
            "github_actions",
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert f"failure_vectors_json={vectors_out}" in stdout
    assert f"failure_vectors_md={vectors_md}" in stdout
    assert "failure_vector_count=1" in stdout

    vector_payload = json.loads(vectors_out.read_text(encoding="utf-8"))
    assert vector_payload["environment"] == "github_actions"
    assert vector_payload["failure_vectors"][0]["command"] == "python -m mypy src"
    assert vector_payload["failure_vectors"][0]["failure_class"] == "type"


def test_ci_failure_extractor_cli_artifacts_cover_dependency_and_unknown_wrapper(
    tmp_path: Path,
    capsys,
) -> None:
    dependency_log = Path("tests/fixtures/ci_failures/dependency_resolver/ci_log.txt")
    unknown_log = Path("tests/fixtures/ci_failures/unknown_wrapper/ci_log.txt")
    failed_logs = tmp_path / "failed-check-logs.json"
    vectors_out = tmp_path / "failure-vectors.json"
    vectors_md = tmp_path / "failure-vectors.md"

    rc = main(
        [
            "--log",
            str(dependency_log),
            "--log",
            str(unknown_log),
            "--out",
            str(failed_logs),
            "--failure-vectors-out",
            str(vectors_out),
            "--failure-vectors-md",
            str(vectors_md),
            "--environment",
            "github_actions",
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert f"failure_vectors_json={vectors_out}" in stdout
    assert f"failure_vectors_md={vectors_md}" in stdout
    assert "failure_vector_count=2" in stdout

    payload = json.loads(vectors_out.read_text(encoding="utf-8"))
    vectors = {item["check"]: item for item in payload["failure_vectors"]}

    dependency = vectors["dependency_resolver"]
    assert dependency["failure_class"] == "dependency"
    assert dependency["risk"] == "high"
    assert dependency["safe_fix_candidate"] is False
    assert dependency["first_failing_line"] == (
        "ERROR: ResolutionImpossible: for help visit https://pip.pypa.io"
    )
    assert dependency["local_repro_command"] is None

    unknown = vectors["unknown_wrapper"]
    assert unknown["failure_class"] == "unknown"
    assert unknown["risk"] == "high"
    assert unknown["safe_fix_candidate"] is False
    assert unknown["exit_code"] == 42
    assert unknown["first_failing_line"] == (
        "custom quality wrapper returned an unexpected integrity result"
    )
    assert unknown["local_repro_command"] is None

    markdown = vectors_md.read_text(encoding="utf-8")
    assert "# Failure Vector Bundle" in markdown
    assert "- `dependency`: `1`" in markdown
    assert "- `unknown`: `1`" in markdown
    assert "custom quality wrapper returned an unexpected integrity result" in markdown
