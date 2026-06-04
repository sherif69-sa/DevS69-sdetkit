from pathlib import Path


def test_makefile_has_release_readiness_start_target() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert "release-readiness-start: release-readiness-workflow" in text
    assert "release-readiness-workflow: venv" in text
    assert "python scripts/release_readiness_start_workflow.py --format json" in text
    assert "python scripts/check_release_readiness_start_summary_contract.py --format json" in text
    assert (
        "python scripts/release_readiness_status_report.py --format json --out build/release-readiness-start/release-readiness-status.json"
        in text
    )
    assert "release-readiness-seed: venv" in text
    assert "python scripts/release_readiness_seed_prerequisites.py" in text
    assert "release-readiness-complete: venv" in text
    assert "python scripts/release_readiness_complete_workflow.py --format json" in text
    assert (
        "python scripts/release_readiness_progress_report.py --format json --out build/release-readiness-complete/release-readiness-progress.json"
        in text
    )
