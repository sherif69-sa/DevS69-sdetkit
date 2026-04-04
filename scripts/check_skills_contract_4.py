#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    required = [
        ROOT / "docs/ultra-upgrade-report-4.md",
        ROOT / "docs/artifacts/skills-sample-4.md",
        ROOT / "src/sdetkit/agent/cli.py",
        ROOT / "tests/test_agent_templates_cli.py",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        print(f"Missing Cycle 4 skills contract files: {', '.join(missing)}", file=sys.stderr)
        return 1

    cli = (ROOT / "src/sdetkit/agent/cli.py").read_text(encoding="utf-8")
    for snippet in ["templates", "run-all", "list"]:
        if snippet not in cli:
            print(f"agent templates CLI missing: {snippet}", file=sys.stderr)
            return 1

    print("skills-contract check passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
