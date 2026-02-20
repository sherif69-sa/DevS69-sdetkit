from __future__ import annotations

import argparse
import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
DAY22_PAGE = Path("docs/integrations-trust-signal-upgrade.md")
DAY22_REPORT = Path("docs/day-22-ultra-upgrade-report.md")
DAY22_ARTIFACT = Path("docs/artifacts/day22-trust-signal-upgrade-sample.md")
DAY22_PACK_SUMMARY = Path("docs/artifacts/day22-trust-pack/day22-trust-summary.json")
DAY22_PACK_SCORECARD = Path("docs/artifacts/day22-trust-pack/day22-trust-scorecard.md")
DAY22_PACK_CHECKLIST = Path("docs/artifacts/day22-trust-pack/day22-visibility-checklist.md")
DAY22_PACK_VALIDATION = Path("docs/artifacts/day22-trust-pack/day22-validation-commands.md")
DAY22_PACK_ACTION_PLAN = Path("docs/artifacts/day22-trust-pack/day22-trust-action-plan.md")
DAY22_EVIDENCE = Path("docs/artifacts/day22-trust-pack/evidence/day22-execution-summary.json")
MODULE = Path("src/sdetkit/trust_signal_upgrade.py")

README_EXPECTED = [
    "## 🔐 Day 22 ultra: trust signal upgrade",
    "python -m sdetkit trust-signal-upgrade --format json --strict",
    "python -m sdetkit trust-signal-upgrade --execute --evidence-dir docs/artifacts/day22-trust-pack/evidence --format json --strict",
    "python scripts/check_day22_trust_signal_upgrade_contract.py",
]
INDEX_EXPECTED = [
    "Day 22 ultra upgrades (trust signal upgrade)",
    "sdetkit trust-signal-upgrade --format json --strict",
    "artifacts/day22-trust-pack/day22-trust-summary.json",
]
CLI_EXPECTED = [
    "## trust-signal-upgrade",
    "--readme",
    "--docs-index",
    "--min-trust-score",
    "--execute",
    "--evidence-dir",
    "--timeout-sec",
    "--emit-pack-dir",
]
PAGE_EXPECTED = [
    "# Trust signal upgrade (Day 22)",
    "## Trust signal inputs",
    "## Fast verification commands",
    "## Scoring model",
    "## Execution evidence mode",
    "## Visibility checklist",
]
REPORT_EXPECTED = ["Day 22 big upgrade", "strict", "--execute", "validation commands"]
SUMMARY_EXPECTED = [
    '"name": "day22-trust-signal-upgrade"',
    '"trust_score":',
    '"governance_checks":',
    '"critical_failures":',
]
EVIDENCE_EXPECTED = ['"name": "day22-trust-signal-upgrade-execution"', '"total_commands": 3']


def _missing(path: Path, expected: list[str]) -> list[str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return [item for item in expected if item not in text]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-evidence", action="store_true")
    ns = ap.parse_args(argv)

    required = [
        README,
        DOCS_INDEX,
        DOCS_CLI,
        DAY22_PAGE,
        DAY22_REPORT,
        DAY22_ARTIFACT,
        DAY22_PACK_SUMMARY,
        DAY22_PACK_SCORECARD,
        DAY22_PACK_CHECKLIST,
        DAY22_PACK_VALIDATION,
        DAY22_PACK_ACTION_PLAN,
        MODULE,
    ]
    if not ns.skip_evidence:
        required.append(DAY22_EVIDENCE)

    errors: list[str] = []
    for path in required:
        if not path.exists():
            errors.append(f"missing required file: {path}")

    if not errors:
        errors.extend(f"{README}: missing '{m}'" for m in _missing(README, README_EXPECTED))
        errors.extend(f"{DOCS_INDEX}: missing '{m}'" for m in _missing(DOCS_INDEX, INDEX_EXPECTED))
        errors.extend(f"{DOCS_CLI}: missing '{m}'" for m in _missing(DOCS_CLI, CLI_EXPECTED))
        errors.extend(f"{DAY22_PAGE}: missing '{m}'" for m in _missing(DAY22_PAGE, PAGE_EXPECTED))
        errors.extend(
            f"{DAY22_REPORT}: missing '{m}'" for m in _missing(DAY22_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f"{DAY22_PACK_SUMMARY}: missing '{m}'"
            for m in _missing(DAY22_PACK_SUMMARY, SUMMARY_EXPECTED)
        )
        if not ns.skip_evidence:
            errors.extend(
                f"{DAY22_EVIDENCE}: missing '{m}'"
                for m in _missing(DAY22_EVIDENCE, EVIDENCE_EXPECTED)
            )

    if errors:
        print("day22-trust-signal-upgrade-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("day22-trust-signal-upgrade-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
