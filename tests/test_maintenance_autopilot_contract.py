from pathlib import Path


def test_baseline_security_check_is_non_blocking_contract() -> None:
    text = Path("tools/maintenance_autopilot.py").read_text(encoding="utf-8")
    marker = 'report["steps"]["baseline_security_check"] = _run('
    assert marker in text
    snippet = text[text.index(marker) : text.index(marker) + 500]
    assert "allow_fail=True" in snippet
