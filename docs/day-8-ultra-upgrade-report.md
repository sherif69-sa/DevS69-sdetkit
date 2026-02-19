# Day 8 Ultra Upgrade Report — Contributor Funnel Start

## Upgrade title

**Day 8 big upgrade: runnable contributor-funnel command with 10 curated good-first-issue tasks and acceptance criteria**

## Problem statement

The repository had a Day 8 plan callout in strategy and weekly review guidance, but no deterministic command output that teams could publish as a ready-to-triage good-first-issue backlog.

Without a generated backlog, first-time contributors face higher discovery friction and maintainers lose consistency in issue quality.

## Implementation scope

### Files changed

- `src/sdetkit/contributor_funnel.py`
  - Added a Day 8 backlog engine that renders 10 curated good-first-issue tasks.
  - Includes explicit acceptance criteria and output formats (`text`, `markdown`, `json`).
  - Added Day 8 validation (`--strict`), area filtering (`--area`), and issue-pack export (`--issue-pack-dir`).
  - Supports writing shareable artifacts with `--output`.
- `src/sdetkit/cli.py`
  - Added top-level command wiring: `python -m sdetkit contributor-funnel ...`.
- `tests/test_contributor_funnel.py`
  - Added coverage for issue count, acceptance criteria completeness, area filtering, and issue-pack artifact export.
- `tests/test_cli_help_lists_subcommands.py`
  - Extended CLI help contract to include `contributor-funnel`.
- `README.md`
  - Added Day 8 section with execution and artifact export commands.
- `docs/index.md`
  - Added Day 8 report link and usage bullets.
- `docs/cli.md`
  - Added `contributor-funnel` command reference.
- `scripts/check_day8_contributor_funnel_contract.py`
  - Added Day 8 contract checker for README/docs/report/script wiring and artifact/module presence.
- `docs/artifacts/day8-good-first-issues-sample.md`
  - Added generated Day 8 backlog artifact sample.

## Validation checklist

- `python -m sdetkit contributor-funnel --format text --strict`
- `python -m sdetkit contributor-funnel --format markdown --output docs/artifacts/day8-good-first-issues-sample.md`
- `python -m sdetkit contributor-funnel --area docs --issue-pack-dir docs/artifacts/day8-issue-pack`
- `python -m pytest -q tests/test_contributor_funnel.py tests/test_cli_help_lists_subcommands.py`
- `python scripts/check_day8_contributor_funnel_contract.py`

## Artifact

This document is the Day 8 artifact report for contributor-funnel backlog bootstrapping.

## Rollback plan

1. Remove `contributor-funnel` command wiring from `src/sdetkit/cli.py`.
2. Remove `src/sdetkit/contributor_funnel.py` and related tests.
3. Revert Day 8 docs/report updates and remove Day 8 artifact/checker script.

Rollback risk is low because this is an additive planning/reporting command and does not alter existing runtime flows.
