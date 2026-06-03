from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_operational_readiness_governance_contract.py"


def test_governance_contract_requires_production_workflow_aliases() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert '"make governance-contract-check"' in text
    assert '"make quality-contract-check"' in text
    assert '"make operational-readiness-governance-contract"' not in text
    assert '"make platform-readiness-quality-contract"' not in text
