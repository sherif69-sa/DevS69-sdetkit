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


def test_safety_gate_decision_consumes_normalized_failure_vector_contract() -> None:
    vector = extract_failure_vector(
        """
        ruff format..............................................................Failed
        tests/test_widget.py
        1 file would be reformatted
        """,
        check="pre-commit / ruff format",
    )

    decision = evaluate_failure_vector(vector)

    assert decision.failure_kind == "formatter_only"
    assert decision.affected_surface == "tests"
    assert decision.ownership_area == "tests/test_widget.py"
    assert decision.retryability == "not_retryable_without_change"
    assert decision.security_relevance is False
    assert decision.reporting_only is True
    assert decision.automation_allowed is False
    assert decision.patch_application_allowed is False
    assert decision.security_dismissal_allowed is False
    assert decision.merge_authorized is False
    assert decision.semantic_equivalence_claim is False
    assert decision.safe_fix_allowed is True
    assert "normalized failure-vector contract" in decision.reason

    payload = decision.to_dict()
    assert payload["failure_kind"] == "formatter_only"
    assert payload["affected_surface"] == "tests"
    assert payload["ownership_area"] == "tests/test_widget.py"

    report = render_safety_gate_decision_report(decision)
    assert "- failure_kind: `formatter_only`" in report
    assert "- affected_surface: `tests`" in report
    assert "- ownership_area: `tests/test_widget.py`" in report
    assert "- retryability: `not_retryable_without_change`" in report
    assert "- reporting_only: `yes`" in report
    assert "- security_dismissal_allowed: `false`" in report
    assert "- merge_authorized: `false`" in report
    assert "- semantic_equivalence_claim: `false`" in report


def test_safety_gate_blocks_contract_that_weakens_authority_boundary() -> None:
    class UnsafeContractVector:
        failure_class = "formatter_only"
        risk = "low"
        scope = "pr_owned_only"
        safe_fix_candidate = True
        affected_files = ("tests/test_widget.py",)
        local_repro_command = "python -m ruff format --check tests/test_widget.py"

        def to_dict(self) -> dict[str, object]:
            return {
                "contract": {
                    "failure_kind": "formatter_only",
                    "affected_surface": "tests",
                    "ownership_area": "tests/test_widget.py",
                    "retryability": "not_retryable_without_change",
                    "security_relevance": False,
                    "recommended_next_human_action": "review generated fix",
                    "reporting_only": True,
                    "automation_allowed": True,
                    "patch_application_allowed": False,
                    "security_dismissal_allowed": False,
                    "merge_authorized": False,
                    "semantic_equivalence_claim": False,
                }
            }

    decision = evaluate_failure_vector(UnsafeContractVector())

    assert decision.safe_fix_allowed is False
    assert decision.review_first is True
    assert decision.allowed_files == ()
    assert "authority boundary" in decision.reason
    assert decision.automation_allowed is True
