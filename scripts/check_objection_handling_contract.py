from __future__ import annotations

import argparse
import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
LANE_PAGE = Path("docs/objection-handling.md")
LANE_REPORT = Path("docs/objection-handling-report.md")
LANE_ARTIFACT = Path("docs/objection-handling.md")
LANE_PACK_SUMMARY = Path("docs/artifacts/objection-handling-pack/objection-handling-summary.json")
LANE_PACK_SCORECARD = Path("docs/artifacts/objection-handling-pack/objection-handling-scorecard.md")
LANE_PACK_MATRIX = Path(
    "docs/artifacts/objection-handling-pack/objection-handling-response-matrix.md"
)
LANE_PACK_PLAYBOOK = Path("docs/artifacts/objection-handling-pack/objection-handling-playbook.md")
LANE_PACK_VALIDATION = Path(
    "docs/artifacts/objection-handling-pack/objection-handling-validation-commands.md"
)
LANE_EVIDENCE = Path(
    "docs/artifacts/objection-handling-pack/evidence/objection-handling-execution-summary.json"
)
MODULE = Path("src/sdetkit/objection_handling.py")

README_EXPECTED = [
    "## Objection handling",
    "python -m sdetkit objection-handling --format json --strict",
    "python -m sdetkit objection-handling --execute --evidence-dir docs/artifacts/objection-handling-pack/evidence --format json --strict",
    "python scripts/check_objection_handling_contract.py",
]
INDEX_EXPECTED = [
    "Objection handling",
    "sdetkit objection-handling --format json --strict",
    "artifacts/objection-handling-pack/objection-handling-summary.json",
]
CLI_EXPECTED = [
    "## objection-handling",
    "--docs-page",
    "--min-faq-score",
    "--execute",
    "--evidence-dir",
    "--timeout-sec",
    "--emit-pack-dir",
]
PAGE_EXPECTED = [
    "# FAQ and objections",
    "## When to use sdetkit",
    "## When not to use sdetkit",
    "## Top objections and responses",
    "## Fast verification commands",
    "## Escalation and rollout policy",
]
REPORT_EXPECTED = ["FAQ and objections report", "strict", "--execute", "Validation commands"]
SUMMARY_EXPECTED = [
    '"name": "objection-handling"',
    '"faq_score":',
    '"critical_failures":',
    '"recommendations":',
]
EVIDENCE_EXPECTED = ['"name": "objection-handling-execution"', '"total_commands": 3']


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
        LANE_PAGE,
        LANE_REPORT,
        LANE_ARTIFACT,
        LANE_PACK_SUMMARY,
        LANE_PACK_SCORECARD,
        LANE_PACK_MATRIX,
        LANE_PACK_PLAYBOOK,
        LANE_PACK_VALIDATION,
        MODULE,
    ]
    if not ns.skip_evidence:
        required.append(LANE_EVIDENCE)

    errors: list[str] = []
    for path in required:
        if not path.exists():
            errors.append(f"missing required file: {path}")

    if not errors:
        errors.extend(f"{README}: missing '{m}'" for m in _missing(README, README_EXPECTED))
        errors.extend(f"{DOCS_INDEX}: missing '{m}'" for m in _missing(DOCS_INDEX, INDEX_EXPECTED))
        errors.extend(f"{DOCS_CLI}: missing '{m}'" for m in _missing(DOCS_CLI, CLI_EXPECTED))
        errors.extend(f"{LANE_PAGE}: missing '{m}'" for m in _missing(LANE_PAGE, PAGE_EXPECTED))
        errors.extend(
            f"{LANE_REPORT}: missing '{m}'" for m in _missing(LANE_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f"{LANE_PACK_SUMMARY}: missing '{m}'"
            for m in _missing(LANE_PACK_SUMMARY, SUMMARY_EXPECTED)
        )
        if not ns.skip_evidence:
            errors.extend(
                f"{LANE_EVIDENCE}: missing '{m}'"
                for m in _missing(LANE_EVIDENCE, EVIDENCE_EXPECTED)
            )

    if errors:
        print("objection-handling-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("objection-handling-contract check passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
