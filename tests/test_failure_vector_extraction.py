from pathlib import Path

from sdetkit.failure_vector import (
    CONTRACT_SCHEMA_VERSION,
    build_failure_vector_bundle,
    extract_failure_vector,
    failure_vector_contract,
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


def test_failure_vector_bundle_report_surfaces_safety_gate_summary(tmp_path: Path) -> None:
    formatter_dir = tmp_path / "ruff-format"
    formatter_dir.mkdir()
    formatter_log = formatter_dir / "log.txt"
    formatter_log.write_text(
        """
        ruff format..............................................................Failed
        tests/test_widget.py
        1 file would be reformatted
        """,
        encoding="utf-8",
    )

    unknown_dir = tmp_path / "custom-wrapper"
    unknown_dir.mkdir()
    unknown_log = unknown_dir / "log.txt"
    unknown_log.write_text(
        """
        custom wrapper failed with unknown output
        Process completed with exit code 42
        """,
        encoding="utf-8",
    )

    payload = build_failure_vector_bundle([formatter_log, unknown_log], environment="local")
    report = render_failure_vector_bundle_report(payload)

    assert "## SafetyGate summary" in report
    assert "- safe_fix_allowed_count: `1`" in report
    assert "- safety_review_first_count: `1`" in report
    assert "- safety_allowed_files: `tests/test_widget.py`" in report
    assert "python -m ruff format --check tests/test_widget.py" in report
    assert "make proof-after-format" in report
    assert "- automation_allowed: `false`" in report
    assert "- patch_application_allowed: `false`" in report
    assert "- merge_authorized: `false`" in report


def test_failure_vector_classifies_dependency_resolver_conflict_review_first() -> None:
    log_text = """
    Run python -m pip install -c constraints-ci.txt -e .[dev,test]
    ERROR: ResolutionImpossible: for help visit https://pip.pypa.io
    Process completed with exit code 1
    """

    vector = extract_failure_vector(
        log_text,
        check="dependency install",
        environment="github_actions",
    )

    assert vector.failure_class == "dependency"
    assert vector.risk == "high"
    assert vector.scope == "unknown"
    assert vector.safe_fix_candidate is False
    assert vector.first_failing_line == (
        "ERROR: ResolutionImpossible: for help visit https://pip.pypa.io"
    )
    assert vector.local_repro_command is None


def test_failure_vector_unknown_wrapper_keeps_first_meaningful_line() -> None:
    log_text = """
    custom quality wrapper returned an unexpected integrity result
    Process completed with exit code 42
    """

    vector = extract_failure_vector(log_text, check="quality wrapper")

    assert vector.failure_class == "unknown"
    assert vector.risk == "high"
    assert vector.scope == "unknown"
    assert vector.safe_fix_candidate is False
    assert vector.exit_code == 42
    assert vector.first_failing_line == (
        "custom quality wrapper returned an unexpected integrity result"
    )
    assert vector.local_repro_command is None


def test_failure_vector_classifies_fixable_ruff_import_sort_lint() -> None:
    log_text = """
    Run python -m ruff check tests/test_widget.py
    I001 [*] Import block is un-sorted or un-formatted
     --> tests/test_widget.py:1:1
    Process completed with exit code 1
    """

    vector = extract_failure_vector(log_text, check="ruff")

    assert vector.failure_class == "lint"
    assert vector.risk == "low"
    assert vector.scope == "pr_owned_only"
    assert vector.safe_fix_candidate is True
    assert vector.first_failing_line == "I001 [*] Import block is un-sorted or un-formatted"
    assert vector.affected_files == ("tests/test_widget.py",)


def test_failure_vector_exposes_starter_fields_for_ruff_lint_failure() -> None:
    log_text = """
    Run python -m pre_commit run -a
    ruff (legacy alias)......................................................Failed
    - hook id: ruff
    - exit code: 1

    F821 Undefined name `JsonObject`
        --> tests/test_pr_quality_action_report.py:3661:6

    Found 1 error.
    Process completed with exit code 1
    """

    vector = extract_failure_vector(
        log_text,
        check="pre-commit / ruff",
        environment="github_actions",
    )

    assert vector.schema_version == "sdetkit.failure_vector.v1"
    assert vector.command == "python -m pre_commit run -a"
    assert vector.failing_command == "python -m pre_commit run -a"
    assert vector.exit_code == 1
    assert vector.failure_class == "lint"
    assert vector.failure_type == "lint"
    assert vector.headline_signal == "pre-commit / ruff: lint"
    assert vector.first_failing_line == (
        "ruff (legacy alias)......................................................Failed"
    )
    assert vector.actual_failure == "F821 Undefined name `JsonObject`"
    assert vector.failing_test_or_check == "F821"
    assert vector.owner_hint == "tests/test_pr_quality_action_report.py"
    assert vector.affected_files == ("tests/test_pr_quality_action_report.py",)
    assert vector.safe_fix_candidate is False
    assert vector.safe_fix_allowed is False


def test_failure_vector_report_renders_starter_fields() -> None:
    vector = extract_failure_vector(
        "Run python -m pre_commit run -a\n"
        "ruff (legacy alias)......................................................Failed\n"
        "F821 Undefined name `JsonObject`\n"
        "    --> tests/test_pr_quality_action_report.py:3661:6\n"
        "Process completed with exit code 1\n",
        check="pre-commit / ruff",
    )

    report = render_failure_vector_report(vector)

    assert "- headline_signal: `pre-commit / ruff: lint`" in report
    assert "- actual_failure: `F821 Undefined name `JsonObject``" in report
    assert "- failure_type: `lint`" in report
    assert "- failing_command: `python -m pre_commit run -a`" in report
    assert "- failing_test_or_check: `F821`" in report
    assert "- owner_hint: `tests/test_pr_quality_action_report.py`" in report
    assert "- safe_fix_allowed: `no`" in report
    assert "- automation_allowed: `false`" in report
    assert "- patch_application_allowed: `false`" in report
    assert "- merge_authorized: `false`" in report


def test_failure_vector_bundle_preserves_starter_fields(tmp_path: Path) -> None:
    log = tmp_path / "pre-commit" / "ruff.log"
    log.parent.mkdir()
    log.write_text(
        "Run python -m pre_commit run -a\n"
        "ruff (legacy alias)......................................................Failed\n"
        "F821 Undefined name `JsonObject`\n"
        "    --> tests/test_pr_quality_action_report.py:3661:6\n"
        "Process completed with exit code 1\n",
        encoding="utf-8",
    )

    payload = build_failure_vector_bundle([log], environment="github_actions")

    vector = payload["failure_vectors"][0]
    assert vector["headline_signal"] == "pre-commit: lint"
    assert vector["actual_failure"] == "F821 Undefined name `JsonObject`"
    assert vector["failure_type"] == "lint"
    assert vector["failing_command"] == "python -m pre_commit run -a"
    assert vector["failing_test_or_check"] == "F821"
    assert vector["owner_hint"] == "tests/test_pr_quality_action_report.py"
    assert vector["safe_fix_allowed"] is False

    report = render_failure_vector_bundle_report(payload)
    assert "- headline_signal: `pre-commit: lint`" in report
    assert "- actual_failure: `F821 Undefined name `JsonObject``" in report
    assert "- safe_fix_allowed: `no`" in report


def test_failure_vector_exposes_normalized_contract() -> None:
    vector = extract_failure_vector(
        "Run PYTHONPATH=src python -m pytest -q\n"
        "FAILED tests/test_widget.py::test_widget_contract - AssertionError\n"
        "Process completed with exit code 1\n",
        check="CI / test",
        environment="github_actions",
    )

    contract = failure_vector_contract(vector)

    assert contract["schema_version"] == CONTRACT_SCHEMA_VERSION
    assert contract["failure_kind"] == "test"
    assert contract["affected_surface"] == "tests"
    assert contract["ownership_area"] == "tests/test_widget.py"
    assert contract["retryability"] == "not_retryable_without_change"
    assert contract["security_relevance"] is False
    assert (
        contract["recommended_next_human_action"]
        == "inspect failing test and affected file before patching"
    )
    assert contract["reporting_only"] is True
    assert contract["automation_allowed"] is False
    assert contract["patch_application_allowed"] is False
    assert contract["security_dismissal_allowed"] is False
    assert contract["merge_authorized"] is False
    assert contract["semantic_equivalence_claim"] is False
    assert vector.to_dict()["contract"] == contract


def test_failure_vector_report_renders_normalized_contract() -> None:
    vector = extract_failure_vector(
        "Run PYTHONPATH=src python -m pytest -q\n"
        "FAILED tests/test_widget.py::test_widget_contract - AssertionError\n",
        check="CI / test",
    )

    report = render_failure_vector_report(vector)

    assert "## Normalized Failure Vector Contract" in report
    assert "- contract_schema_version: `sdetkit.failure_vector.contract.v1`" in report
    assert "- failure_kind: `test`" in report
    assert "- affected_surface: `tests`" in report
    assert "- ownership_area: `tests/test_widget.py`" in report
    assert "- retryability: `not_retryable_without_change`" in report
    assert "- reporting_only: `true`" in report
    assert "- automation_allowed: `false`" in report
    assert "- patch_application_allowed: `false`" in report
    assert "- security_dismissal_allowed: `false`" in report
    assert "- merge_authorized: `false`" in report
    assert "- semantic_equivalence_claim: `false`" in report
