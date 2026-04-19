from pathlib import Path


def test_makefile_has_phase2_start_target() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert "phase2-start: phase2-workflow" in text
    assert "phase2-workflow: venv" in text
    assert "python scripts/phase2_start_workflow.py --format json" in text
    assert "python scripts/check_phase2_start_summary_contract.py --format json" in text
    assert "python scripts/phase2_status_report.py --format json --out build/phase2-start/phase2-status.json" in text
    assert "phase2-seed: venv" in text
    assert "python scripts/phase2_seed_prerequisites.py" in text
    assert "phase2-complete: venv" in text
    assert "python scripts/phase2_complete_workflow.py --format json" in text
    assert "python scripts/phase2_progress_report.py --format json --out build/phase2-complete/phase2-progress.json" in text
