from pathlib import Path


def test_makefile_has_bootstrap_and_max_targets() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert "bootstrap: venv" in text
    assert "max: bootstrap" in text
    assert "bash scripts/bootstrap.sh" in text
    assert "bash quality.sh boost" in text
