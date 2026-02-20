from __future__ import annotations

import argparse
import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
DAY20_PAGE = Path("docs/integrations-release-narrative.md")
DAY20_REPORT = Path("docs/day-20-ultra-upgrade-report.md")
DAY20_ARTIFACT = Path("docs/artifacts/day20-release-narrative-sample.md")
DAY20_PACK_SUMMARY = Path(
    "docs/artifacts/day20-release-narrative-pack/day20-release-narrative-summary.json"
)
DAY20_PACK_MD = Path("docs/artifacts/day20-release-narrative-pack/day20-release-narrative.md")
DAY20_PACK_BLURBS = Path("docs/artifacts/day20-release-narrative-pack/day20-audience-blurbs.md")
DAY20_PACK_CHANNELS = Path("docs/artifacts/day20-release-narrative-pack/day20-channel-posts.md")
DAY20_PACK_VALIDATION = Path(
    "docs/artifacts/day20-release-narrative-pack/day20-validation-commands.md"
)
DAY20_EVIDENCE = Path(
    "docs/artifacts/day20-release-narrative-pack/evidence/day20-execution-summary.json"
)
MODULE = Path("src/sdetkit/release_narrative.py")

README_EXPECTED = [
    "## ✍️ Day 20 ultra: release narrative",
    "python -m sdetkit release-narrative --format json --strict",
    "python -m sdetkit release-narrative --execute --evidence-dir docs/artifacts/day20-release-narrative-pack/evidence --format json --strict",
    "python scripts/check_day20_release_narrative_contract.py",
]
INDEX_EXPECTED = [
    "Day 20 ultra upgrades (release narrative)",
    "sdetkit release-narrative --format json --strict",
    "artifacts/day20-release-narrative-pack/day20-channel-posts.md",
]
CLI_EXPECTED = [
    "## release-narrative",
    "--day19-summary",
    "--changelog",
    "--min-release-score",
    "--execute",
    "--evidence-dir",
    "--timeout-sec",
    "--emit-pack-dir",
]
PAGE_EXPECTED = [
    "# Release narrative (Day 20)",
    "## Story inputs",
    "## Fast verification commands",
    "## Execution evidence mode",
    "## Narrative channels",
]
REPORT_EXPECTED = ["Day 20 big upgrade", "strict", "--execute", "validation commands"]
SUMMARY_EXPECTED = [
    '"name": "day20-release-narrative"',
    '"readiness_label":',
    '"narrative_channels":',
]
EVIDENCE_EXPECTED = ['"name": "day20-release-narrative-execution"', '"total_commands": 3']


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
        DAY20_PAGE,
        DAY20_REPORT,
        DAY20_ARTIFACT,
        DAY20_PACK_SUMMARY,
        DAY20_PACK_MD,
        DAY20_PACK_BLURBS,
        DAY20_PACK_CHANNELS,
        DAY20_PACK_VALIDATION,
        MODULE,
    ]
    if not ns.skip_evidence:
        required.append(DAY20_EVIDENCE)

    errors: list[str] = []
    for path in required:
        if not path.exists():
            errors.append(f"missing required file: {path}")

    if not errors:
        errors.extend(f"{README}: missing '{m}'" for m in _missing(README, README_EXPECTED))
        errors.extend(f"{DOCS_INDEX}: missing '{m}'" for m in _missing(DOCS_INDEX, INDEX_EXPECTED))
        errors.extend(f"{DOCS_CLI}: missing '{m}'" for m in _missing(DOCS_CLI, CLI_EXPECTED))
        errors.extend(f"{DAY20_PAGE}: missing '{m}'" for m in _missing(DAY20_PAGE, PAGE_EXPECTED))
        errors.extend(
            f"{DAY20_REPORT}: missing '{m}'" for m in _missing(DAY20_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f"{DAY20_PACK_SUMMARY}: missing '{m}'"
            for m in _missing(DAY20_PACK_SUMMARY, SUMMARY_EXPECTED)
        )
        if not ns.skip_evidence:
            errors.extend(
                f"{DAY20_EVIDENCE}: missing '{m}'"
                for m in _missing(DAY20_EVIDENCE, EVIDENCE_EXPECTED)
            )

    if errors:
        print("day20-release-narrative-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("day20-release-narrative-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
