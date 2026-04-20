from __future__ import annotations

from pathlib import Path


def test_makefile_has_adaptive_premerge_target() -> None:
    text = Path("Makefile").read_text(encoding="utf-8")
    assert "adaptive-premerge: adaptive-scenario-db" in text
    assert "--scenario strict" in text
    assert "--history-json build/adaptive-postcheck-history.json" in text
