from __future__ import annotations

from pathlib import Path


def test_phase3_operational_workflow_wired() -> None:
    workflow = Path('.github/workflows/phase3-quality-contract.yml')
    text = workflow.read_text(encoding='utf-8')

    assert "name: phase3-quality-contract" in text
    assert "make phase3-do-it" in text
    assert "phase3-quality-artifacts" in text
    assert "build/phase3-quality/*.json" in text
    assert "build/phase1-baseline/history/*.json" in text


def test_phase3_do_it_target_exists() -> None:
    text = Path("Makefile").read_text(encoding="utf-8")
    assert "phase3-do-it: phase3-quality-contract" in text
    assert "python -m scripts.build_phase3_trend_delta" in text
