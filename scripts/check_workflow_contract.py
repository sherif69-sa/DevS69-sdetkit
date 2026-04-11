from __future__ import annotations

import sys
from pathlib import Path

WORKFLOW = Path("WORKFLOW.md")

REQUIRED_SECTIONS = [
    "## Zero-friction startup (run this first)",
    "## Tier 1 — Daily / PR lane (default)",
    "## Tier 2 — Weekly health lane (scheduled)",
    "## Tier 3 — Release-day / advanced lane (opt-in)",
    "## Default ignore list (to reduce context switching)",
    "## Quick run checklist",
    "## PR clean policy (every PR)",
]

REQUIRED_COMMANDS = [
    "python -m sdetkit gate fast",
    "python -m sdetkit gate release",
    "python -m sdetkit doctor",
    "PYTHONPATH=src pytest -q",
    "bash quality.sh cov",
    "ruff check .",
    "mutmut results",
    "python scripts/pr_clean.py --size <small|medium|large> --run",
    "python scripts/start_session.py --size <small|medium|large> --run",
    "python -m sdetkit review . --no-workspace --format operator-json",
    "cat .sdetkit/pr-clean-report.json",
]


def _missing(text: str, required: list[str]) -> list[str]:
    return [item for item in required if item not in text]


def main() -> int:
    if not WORKFLOW.exists():
        print(f"workflow-contract check failed: missing required file: {WORKFLOW}", file=sys.stderr)
        return 1

    text = WORKFLOW.read_text(encoding="utf-8")
    errors: list[str] = []

    for item in _missing(text, REQUIRED_SECTIONS):
        errors.append(f'missing section: "{item}"')
    for item in _missing(text, REQUIRED_COMMANDS):
        errors.append(f'missing command: "{item}"')

    if errors:
        print("workflow-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("workflow-contract check passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
