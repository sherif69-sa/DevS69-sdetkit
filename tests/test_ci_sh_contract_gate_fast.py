from __future__ import annotations

from pathlib import Path


def test_ci_sh_quick_uses_gate_fast_and_emits_artifact() -> None:
    text = Path("ci.sh").read_text(encoding="utf-8")
    assert "python3 -m sdetkit gate fast" in text
    assert "--stable-json" in text
    assert "--artifact-dir" in text
    assert "gate-fast.json" in text
    assert "python3 -m pytest -q" not in text
