# Cycle 11 Ultra Upgrade Report — Docs Navigation Tune-Up

## Snapshot

**Cycle 11 big upgrade: shipped a runnable docs-navigation command plus contract checks so top user journeys are one-click from docs home.**

## Problem statement

The docs home page had many valuable links, but maintainers lacked an executable guard proving that the highest-value journeys stayed visible and one-click after edits.

## What shipped

### Product code

- `src/sdetkit/docs_navigation.py`
  - Added Cycle 11 docs-navigation engine with text/markdown/json output and strict validation.
  - Added `--root` support for validating arbitrary repository targets.
  - Added `--strict` mode to fail when required one-click links or journey content is missing from `docs/index.md`.
  - Added `--write-defaults` mode to repair quick-jump defaults, restore the Cycle 11 section header + top-journey block, and bootstrap `docs/index.md` when missing.
- `src/sdetkit/cli.py`
  - Added top-level command wiring: `python -m sdetkit docs-nav ...`.

### Docs surface

- `README.md`
  - Added Cycle 11 section, runnable commands, artifact export flow, and closeout checks.
- `docs/index.md`
  - Added Cycle 11 report link in quick-jump and Cycle 11 top-journey section.
- `docs/cli.md`
  - Added `docs-nav` command reference and strict/recovery flag guidance.

### Tests and checks

- `tests/test_docs_navigation.py`
  - Added rendering, strict-pass, strict-fail, write-defaults recovery, docs-index bootstrap, and CLI-dispatch coverage.
- `tests/test_cli_help_lists_subcommands.py`
  - Added `docs-nav` subcommand contract assertion.
- `scripts/check_docs_navigation_contract_11.py`
  - Added Cycle 11 contract checker for README/docs/report/artifact wiring.

## Validation checklist

- `python -m pytest -q tests/test_docs_navigation.py tests/test_cli_help_lists_subcommands.py`
- `python scripts/check_docs_navigation_contract_11.py`
- `python -m sdetkit docs-nav --format json --strict`
- `python -m sdetkit docs-nav --write-defaults --format json --strict`
- `python -m sdetkit docs-nav --format markdown --output docs/artifacts/docs-governance-sample.md`

## Artifacts

- `docs/artifacts/docs-governance-sample.md`

## Rollback plan

1. Revert `src/sdetkit/docs_navigation.py` and remove `docs-nav` wiring from `src/sdetkit/cli.py`.
2. Revert Cycle 11 sections in `README.md`, `docs/index.md`, and `docs/cli.md`.
3. Remove Cycle 11 tests/checker/report/artifact if rolling back this feature.

This document is the Cycle 11 artifact report for docs-home navigation hardening.
