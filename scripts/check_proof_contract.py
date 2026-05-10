#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    required = [
        ROOT / "docs/evidence-assets-report.md",
        ROOT / "src/sdetkit/proof.py",
        ROOT / "tests/test_proof_cli.py",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        print(f"Missing Cycle 3 proof contract files: {', '.join(missing)}", file=sys.stderr)
        return 1

    cli = (ROOT / "src/sdetkit/cli.py").read_text(encoding="utf-8")
    if '"proof",' not in cli and '{"evidence-assets", "proof"}' not in cli:
        print("CLI must expose proof command", file=sys.stderr)
        return 1

    print("proof-contract check passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
