from pathlib import Path


def test_makefile_has_phase1_do_it_target() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert "phase1-do-it: phase1-run-all phase1-artifact-set phase1-telemetry phase1-finish-signal" in text
