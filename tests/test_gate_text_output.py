"""`gate fast`'s terminal output leads with the verdict, like its Markdown summary.

It used to print `gate fast: OK` or `gate fast: FAIL`, then a `next_action:` block whose
`decision` read `CONTINUE` or `NO-SHIP`, never the verdict. In an empty repository it read
`OK`, `decision: CONTINUE` and `next_command: ... gate release`, while the verdict was
NOT_RUN: nothing had been checked.
"""

from __future__ import annotations

from typing import Any

from sdetkit import adaptive_diagnosis, gate

STEP_OK = {"id": "ruff", "ok": True, "rc": 0, "duration_ms": 4}


def _payload(decision: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": decision in {"SHIP", "NOT_RUN"},
        "steps": [STEP_OK],
        "failed_steps": [],
        "verdict": {"decision": decision, "reasons": [], "next_action": ""},
        "environment": {"python": "/repo/.venv/bin/python", "source": ".venv"},
    }
    payload.update(extra)
    return payload


def test_ship_reads_the_verdict_its_meaning_and_the_next_command() -> None:
    payload = _payload("SHIP")
    payload["verdict"]["next_action"] = "python -m sdetkit gate release"

    assert gate._format_text(payload) == (
        "SDETKit gate fast: SHIP\n"
        "Every check ran against this repository and passed.\n"
        "python: /repo/.venv/bin/python (.venv)\n"
        "[OK] ruff (4ms) rc=0\n"
        "next: python -m sdetkit gate release\n"
    )


def test_nothing_checked_says_why_and_follows_the_verdict_not_the_card() -> None:
    payload = _payload(
        "NOT_RUN",
        steps=[],
        skipped_steps=[{"id": "pytest", "reason": "no tests detected"}],
        next_action={"decision": "CONTINUE", "next_command": "python -m sdetkit gate release"},
    )
    payload["verdict"]["reasons"] = ["nothing in this repository was checked"]
    payload["verdict"]["next_action"] = "Add tests, then run: python -m sdetkit gate fast"

    text = gate._format_text(payload)

    assert text.startswith("SDETKit gate fast: NOT_RUN\n")
    assert "[SKIP] pytest: no tests detected\n" in text
    assert "why: nothing in this repository was checked\n" in text
    assert text.endswith("next: Add tests, then run: python -m sdetkit gate fast\n")
    assert "gate release" not in text and "CONTINUE" not in text


def test_an_environment_problem_is_not_run_and_is_said_once() -> None:
    problem = "pytest could not import this project's own package 'calc'"
    payload = _payload(
        "NOT_RUN",
        steps=[
            STEP_OK,
            {
                "id": "pytest",
                "ok": False,
                "rc": 2,
                "duration_ms": 9,
                "environment_problem": problem,
            },
        ],
        failed_steps=["pytest"],
        next_action={"first_failure": problem, "classification": "environment"},
    )
    payload["verdict"]["reasons"] = [f"pytest did not run against this repository: {problem}"]
    payload["verdict"]["next_action"] = "uv sync && python -m sdetkit gate fast"

    text = gate._format_text(payload)

    assert "[NOT RUN] pytest (9ms) rc=2\n" in text
    assert f"first failure (environment): {problem}\n" in text
    assert "why:" not in text
    assert "next: uv sync && python -m sdetkit gate fast\n" in text


def test_a_failure_names_its_file_once_and_lists_other_recommendations() -> None:
    payload = _payload(
        "NO_SHIP",
        steps=[STEP_OK, {"id": "pytest", "ok": False, "rc": 1, "duration_ms": 7}],
        failed_steps=["pytest", "configuration"],
        recommendations=["python -m pytest -q tests/test_a.py::test_x", "fix the config"],
        next_action={
            "first_failure": "FAILED tests/test_a.py::test_x - assert 1 == 2",
            "affected_file": "tests/test_a.py",
            "classification": "test",
            "next_command": "python -m pytest -q tests/test_a.py::test_x",
        },
    )
    payload["verdict"]["reasons"] = ["step failed: pytest"]

    text = gate._format_text(payload)

    assert text.startswith("SDETKit gate fast: NO_SHIP\nA check failed.\n")
    assert "[FAIL] pytest (7ms) rc=1\n[FAIL] configuration\n" in text
    assert "first failure (test): FAILED tests/test_a.py::test_x - assert 1 == 2\n" in text
    assert "next: python -m pytest -q tests/test_a.py::test_x\nalso: fix the config\n" in text
    assert "why:" not in text


def test_ci_log_scanning_reads_the_new_header() -> None:
    assert adaptive_diagnosis._has_green_quality_gate_signal("SDETKit gate fast: SHIP")
    for header in ("SDETKit gate fast: NO_SHIP", "SDETKit gate fast: NOT_RUN"):
        lowered = header.lower()
        assert any(
            t in lowered for t in adaptive_diagnosis.HARD_FAILURE_TOKENS_IN_GREEN_GATE_CONTEXT
        )
