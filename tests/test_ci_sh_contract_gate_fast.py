from __future__ import annotations

from pathlib import Path


def test_ci_sh_quick_uses_gate_fast_and_emits_artifact() -> None:
    text = Path("ci.sh").read_text(encoding="utf-8")
    assert "python3 -m sdetkit gate fast" in text
    assert "--stable-json" in text
    assert "--artifact-dir" in text
    assert "gate-fast.json" in text
    assert "--no-mypy" in text
    assert "python3 -m pytest -q" not in text


def test_ci_sh_runs_operational_maturity_v2_checks() -> None:
    text = Path("ci.sh").read_text(encoding="utf-8")
    assert "run_operational_maturity_v2" in text
    assert "scripts/legacy_command_analyzer.py --format json" in text
    assert "scripts/legacy_burndown.py" in text
    assert "scripts/adoption_scorecard.py --format json" in text
    assert "scripts/check_adoption_scorecard_v2_contract.py" in text
