from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_phase4_governance_contract.py"


def test_governance_contract_requires_production_workflow_aliases() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert '"make governance-contract-check"' in text
    assert '"make quality-contract-check"' in text
    assert '"make phase4-governance-contract"' not in text
    assert '"make phase3-quality-contract"' not in text
