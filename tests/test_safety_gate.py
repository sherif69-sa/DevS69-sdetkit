from pathlib import Path
from types import SimpleNamespace

from sdetkit.failure_vector import extract_failure_vector
from sdetkit.safety_gate import (
    evaluate_failure_vector,
    render_safety_gate_decision_report,
    write_safety_gate_decision,
)


def test_safety_gate_allows_formatter_only_pr_owned_vector() -> None:
    vector = extract_failure_vector(
        """
        ruff format..............................................................Failed
        tests/test_widget.py
        1 file would be reformatted
        """,
        check="pre-commit / ruff format",
    )

    decision = evaluate_failure_vector(vector)

    assert decision.schema_version == "sdetkit.safety_gate.v1"
    assert decision.safe_fix_allowed is True
    assert decision.review_first is False
    assert decision.allowed_files == ("tests/test_widget.py",)
    assert decision.proof_commands == (
        "python -m ruff format --check tests/test_widget.py",
        "make proof-after-format",
    )


def test_safety_gate_allows_import_sort_lint_only_when_vector_is_safe_candidate() -> None:
    vector = extract_failure_vector(
        """
        Run python -m ruff check tests/test_widget.py
        I001 [*] Import block is un-sorted or un-formatted
         --> tests/test_widget.py:1:1
        Process completed with exit code 1
        """,
        check="ruff",
    )

    decision = evaluate_failure_vector(vector)

    assert vector.failure_class == "lint"
    assert vector.safe_fix_candidate is True
    assert decision.safe_fix_allowed is True
    assert decision.allowed_files == ("tests/test_widget.py",)


def test_safety_gate_blocks_safe_candidate_without_required_proof_command() -> None:
    vector = SimpleNamespace(
        failure_class="formatter_only",
        risk="low",
        scope="pr_owned_only",
        safe_fix_candidate=True,
        affected_files=("tests/test_widget.py",),
        local_repro_command=None,
    )

    decision = evaluate_failure_vector(vector)

    assert decision.safe_fix_allowed is False
    assert decision.review_first is True
    assert decision.allowed_files == ()
    assert "local repro command" in decision.reason


def test_safety_gate_blocks_unknown_failure_review_first() -> None:
    vector = extract_failure_vector(
        """
        custom quality wrapper returned an unexpected integrity result
        Process completed with exit code 42
        """,
        check="quality wrapper",
    )

    decision = evaluate_failure_vector(vector)

    assert decision.safe_fix_allowed is False
    assert decision.review_first is True
    assert decision.allowed_files == ()
    assert "unknown" in decision.reason


def test_safety_gate_blocks_safe_candidate_without_scope() -> None:
    vector = extract_failure_vector(
        """
        ruff format..............................................................Failed
        1 file would be reformatted
        """,
        check="pre-commit / ruff format",
    )

    decision = evaluate_failure_vector(vector)

    assert vector.safe_fix_candidate is True
    assert vector.scope == "unknown"
    assert decision.safe_fix_allowed is False
    assert "affected files" in decision.reason


def test_safety_gate_report_and_json_are_deterministic(tmp_path: Path) -> None:
    vector = extract_failure_vector(
        """
        ruff format..............................................................Failed
        tests/test_widget.py
        1 file would be reformatted
        """,
        check="pre-commit / ruff format",
    )
    decision = evaluate_failure_vector(vector)
    out = tmp_path / "build" / "sdetkit" / "safety-gate-decision.json"

    write_safety_gate_decision(decision, out)
    report = render_safety_gate_decision_report(decision)

    text = out.read_text(encoding="utf-8")
    assert '"schema_version": "sdetkit.safety_gate.v1"' in text
    assert '"safe_fix_allowed": true' in text
    assert "# Safety Gate Decision" in report
    assert "- safe_fix_allowed: `yes`" in report
    assert "- allowed_files: `tests/test_widget.py`" in report
