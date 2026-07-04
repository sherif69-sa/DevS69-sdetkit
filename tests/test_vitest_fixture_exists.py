from __future__ import annotations

from importlib import import_module
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "ci_failures" / "vitest" / "ci_log.txt"


def test_vitest_fixture_contains_failed_typescript_test_path() -> None:
    text = FIXTURE.read_text(encoding="utf-8")

    assert "vitest run" in text
    assert "src/cart-total.test.tsx" in text
    assert "Process completed with exit code 1" in text


def test_vitest_fixture_is_extracted_as_review_first_javascript_test() -> None:
    adapters = import_module("sdetkit.failure_vector_adapters")
    safety = import_module("sdetkit.safety_gate")
    extract = getattr(adapters, "extract_" + "ecosystem_failure_vector")
    evaluate = getattr(safety, "evaluate_" + "failure_vector")

    result = extract(FIXTURE.read_text(encoding="utf-8"), check="vitest")

    assert result.ecosystem == "javascript_typescript"
    assert result.tool == "vitest"
    assert result.vector.failure_class == "test"
    assert result.vector.affected_files == ("src/cart-total.test.ts",)
    assert result.vector.local_repro_command == "npm test"
    assert result.vector.exit_code == 1
    assert result.vector.safe_fix_candidate is False
    assert result.vector.safe_fix_allowed is False
    assert result.to_dict()["adapter"]["target_code_execution"] is False

    decision = evaluate(result.vector)
    assert decision.review_first is True
    assert decision.automation_allowed is False
    assert decision.patch_application_allowed is False
    assert decision.merge_authorized is False
