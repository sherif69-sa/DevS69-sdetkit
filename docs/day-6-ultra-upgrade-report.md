# Cycle 6 Ultra Upgrade Report — Conversion QA Hardening

## Upgrade title

**Cycle 6 big upgrade: runnable conversion QA gate for README/docs links + anchors**

## Problem statement

Users evaluating the project from README and docs were exposed to conversion friction when internal links or anchor references drifted.

This made first-command onboarding brittle and slowed trust-building during repo exploration.

## Implementation scope

### Files changed

- `src/sdetkit/docs_qa.py`
  - Added a Cycle 6 docs QA engine that scans `README.md` and all `docs/**/*.md` files.
  - Validates local anchors (`#...`), inline/reference markdown links, and markdown target anchors.
  - Ignores fenced code blocks to prevent false positives from command examples.
  - Supports duplicate heading anchors (`-1`, `-2`, ...) for GitHub-compatible slug matching.
  - Added JSON/text/markdown report output with deterministic pass/fail exit codes.
- `src/sdetkit/cli.py`
  - Added top-level `docs-qa` command wiring: `python -m sdetkit docs-qa ...`.
- `tests/test_docs_qa.py`
  - Added positive repo-level docs QA coverage.
  - Added failure-path coverage for missing anchors in a temporary markdown fixture.
- `tests/test_cli_help_lists_subcommands.py`
  - Extended CLI help contract to include `docs-qa` in `sdetkit --help` output.
- `README.md`
  - Added Cycle 5 onboarding boost section for continuity.
  - Added Cycle 6 conversion QA section with runnable command flow and closeout checks.
  - Corrected Phase-1 strategy anchor target used in links.
- `docs/index.md`
  - Added Cycle 5 and Cycle 6 report links plus execution bullets.
  - Corrected strategy anchor links for impact-plan navigation.
- `docs/cli.md`
  - Added `docs-qa` command reference and usage examples.
- `docs/artifacts/cycle1-onboarding-sample.md`
  - Fixed repo-relative README link path for docs artifact navigation.
- `docs/artifacts/cycle2-demo-sample.md`
  - Fixed repo-relative README and repo-audit link paths.
- `docs/artifacts/cycle5-platform-onboarding-sample.md`
  - Fixed repo-relative README link path.
- `scripts/check_day6_conversion_contract.py`
  - Added Cycle 6 contract checker to assert README/docs/report/script wiring and artifact presence.
- `docs/artifacts/cycle6-conversion-qa-sample.md`
  - Added generated Cycle 6 QA artifact sample.

## Validation checklist

- `python -m sdetkit docs-qa --format text`
- `python -m sdetkit docs-qa --format markdown --output docs/artifacts/cycle6-conversion-qa-sample.md`
- `python -m pytest -q tests/test_docs_qa.py tests/test_cli_help_lists_subcommands.py`
- `python scripts/check_day6_conversion_contract.py`

## Artifact

This document is the Cycle 6 artifact report for conversion QA hardening and onboarding friction removal.

## Rollback plan

1. Remove `docs-qa` command wiring from `src/sdetkit/cli.py`.
2. Remove `src/sdetkit/docs_qa.py` and related tests.
3. Revert Cycle 6 docs/report updates and remove Cycle 6 artifact/checker script.

Rollback risk is low because this is additive validation behavior and does not change existing command semantics.
