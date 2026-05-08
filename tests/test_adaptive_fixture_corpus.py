from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import adaptive_diagnosis

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "adaptive_logs"
METADATA = json.loads((FIXTURE_DIR / "metadata.json").read_text(encoding="utf-8"))


def _all_text(values: object) -> str:
    return json.dumps(values, sort_keys=True)


@pytest.mark.parametrize("case", METADATA, ids=[row["file"] for row in METADATA])
def test_top_scenario_fixture_corpus_preserves_expected_diagnosis(case: dict[str, object]) -> None:
    log_text = (FIXTURE_DIR / str(case["file"])).read_text(encoding="utf-8")

    payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)

    assert payload["diagnoses"], case["file"]
    diagnosis = payload["diagnoses"][0]
    assert diagnosis["code"] == case["primary"]
    assert case["proof_contains"] in _all_text(diagnosis["proof_commands"])
    assert payload["fix_plan"][0]["safe_to_auto_fix"] is case["safe"]
    if candidate := case.get("candidate"):
        assert candidate in _all_text(diagnosis["evidence"])


def test_top_scenario_fixture_corpus_covers_at_least_twenty_realistic_logs() -> None:
    assert len(METADATA) >= 20
    assert {row["primary"] for row in METADATA} >= {
        "PYTEST_ASSERTION_FAILURE",
        "PYTEST_IMPORT_FAILURE",
        "PRE_COMMIT_FORMAT_DRIFT",
        "RUFF_FIXABLE_LINT",
        "RUFF_LINT_FAILURE",
        "MYPY_TYPE_CONTRACT_DRIFT",
        "UNKNOWN_REVIEW_REQUIRED",
    }
