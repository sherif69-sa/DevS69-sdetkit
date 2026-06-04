from pathlib import Path


def test_makefile_has_baseline_do_it_target() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert (
        "baseline-run: baseline-run-all baseline-artifact-set baseline-telemetry baseline-readiness-signal"
        in text
    )
