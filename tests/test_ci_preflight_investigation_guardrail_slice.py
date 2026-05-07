from __future__ import annotations

from pathlib import Path


def test_ci_preflight_runs_investigation_and_guardrail_slice() -> None:
    text = Path("scripts/ci.sh").read_text(encoding="utf-8")

    assert "run_investigation_guardrail_slice()" in text
    assert "tests/test_investigate_cli.py" in text
    assert "tests/test_investigate_failure.py" in text
    assert "tests/test_investigation_chain_no_mutation.py" in text
    assert "tests/test_pr_guardrail_decisions.py" in text
    assert "tests/test_maintenance_autopilot_safe_commit.py" in text


def test_ci_quick_and_all_modes_include_investigation_guardrail_slice() -> None:
    text = Path("scripts/ci.sh").read_text(encoding="utf-8")
    quick_case = text.split("quick)", 1)[1].split(";;", 1)[0]
    all_case = text.split("all)", 1)[1].split(";;", 1)[0]

    assert "run_gate_fast" in quick_case
    assert "run_investigation_guardrail_slice" in quick_case
    assert "run_flagship_contracts" in quick_case

    assert "run_gate_fast" in all_case
    assert "run_investigation_guardrail_slice" in all_case
    assert "run_flagship_contracts" in all_case
