from __future__ import annotations

from pathlib import Path

README = Path("README.md").read_text(encoding="utf-8")
START_HERE = Path("docs/start-here-5-minutes.md").read_text(encoding="utf-8")
TRIAGE = Path("docs/first-failure-triage.md").read_text(encoding="utf-8")

CANONICAL_DOCTOR = "python -m sdetkit doctor --format json --out build/doctor.json"


def test_start_here_doctor_matches_readme_first_run() -> None:
    assert CANONICAL_DOCTOR in README
    assert CANONICAL_DOCTOR in START_HERE
    assert "python -m sdetkit doctor\n" not in START_HERE


def test_first_failure_triage_stays_on_canonical_path() -> None:
    assert "python -m sdetkit gate fast" in TRIAGE
    assert "python -m sdetkit gate release" in TRIAGE
    assert "python -m sdetkit doctor" in TRIAGE
    assert "python -m sdetkit investigate" in TRIAGE
    assert "security enforce" not in TRIAGE


def test_first_failure_triage_points_to_one_next_action() -> None:
    assert "next_action" in TRIAGE or "first failed quality step" in TRIAGE
    assert "python -m sdetkit investigate failure" in TRIAGE
