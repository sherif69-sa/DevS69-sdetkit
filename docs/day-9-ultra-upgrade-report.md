# Day 9 Ultra Upgrade Report — Contribution Template Triage

## Snapshot

**Day 9 big upgrade: hardened issue/PR templates plus runnable triage-template validation command**

## Problem statement

The repository had baseline issue and PR templates, but triage-critical fields (severity, impact, acceptance criteria, risk, rollback) were optional or absent. This created avoidable maintainer back-and-forth and slower response times for first-time contributors.

## What shipped

### Product code

- `src/sdetkit/triage_templates.py`
  - Added a Day 9 template-health engine that checks bug, feature, and PR templates for required triage tokens.
  - Added text/markdown/json output formats.
  - Added strict mode for CI gating.
- `src/sdetkit/cli.py`
  - Added top-level command wiring: `python -m sdetkit triage-templates ...`.

### Contribution surface

- `.github/ISSUE_TEMPLATE/bug_report.yml`
  - Added severity dropdown, user impact, expected/actual behavior, and required environment details.
- `.github/ISSUE_TEMPLATE/feature_request.yml`
  - Added problem statement naming, acceptance criteria block, priority dropdown, and ownership field.
- `.github/PULL_REQUEST_TEMPLATE.md`
  - Added explicit risk assessment, test evidence, rollback plan, and triage ownership prompts.

### Tests and checks

- `tests/test_triage_templates.py`
  - Added payload, markdown export, and SLA contract checks.
- `tests/test_cli_help_lists_subcommands.py`
  - Extended CLI help contract to include `triage-templates`.
- `scripts/check_day9_contribution_templates_contract.py`
  - Added Day 9 contract checker for README/docs/report/script wiring.

### Docs and artifacts

- `README.md`
  - Added Day 9 section with command usage and closeout checks.
- `docs/index.md`
  - Added Day 9 quick-jump link and upgrade section.
- `docs/cli.md`
  - Added `triage-templates` command reference.
- `docs/artifacts/day9-triage-templates-sample.md`
  - Added generated Day 9 template-health artifact sample.

## Validation checklist

- `python -m pytest -q tests/test_triage_templates.py tests/test_cli_help_lists_subcommands.py`
- `python scripts/check_day9_contribution_templates_contract.py`
- `python -m sdetkit triage-templates --format json --strict`

## Artifacts

- `docs/artifacts/day9-triage-templates-sample.md`

## Rollback plan

1. Remove `triage-templates` command wiring from `src/sdetkit/cli.py`.
2. Revert template changes in `.github/ISSUE_TEMPLATE/*.yml` and `.github/PULL_REQUEST_TEMPLATE.md`.
3. Remove Day 9 docs/report updates and delete the Day 9 contract checker.

This document is the Day 9 artifact report for contribution-template triage hardening.
