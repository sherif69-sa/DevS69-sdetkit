# Day 9 Ultra Upgrade Report — Contribution Template Triage

## Snapshot

**Day 9 big upgrade: hardened issue/PR/config templates plus runnable triage-template validation and auto-recovery command**

## Problem statement

The repository had baseline issue and PR templates, but template quality checks were shallow and did not validate `.github/ISSUE_TEMPLATE/config.yml` posture. Teams could still drift into triage gaps that slowed maintainer response.

## What shipped

### Product code

- `src/sdetkit/triage_templates.py`
  - Expanded Day 9 engine to validate structured requirements across bug, feature, PR, and issue-template config files.
  - Added repository root targeting (`--root`) for local/CI checks across arbitrary paths.
  - Added auto-recovery path (`--write-defaults`) that writes hardened baseline templates, then re-validates.
  - Added richer reporting payload with missing checks, actions, and touched-files output.
- `src/sdetkit/cli.py`
  - Retained top-level command wiring: `python -m sdetkit triage-templates ...`.

### Contribution surface

- `.github/ISSUE_TEMPLATE/bug_report.yml`
  - Hardened for triage-critical IDs and required fields.
- `.github/ISSUE_TEMPLATE/feature_request.yml`
  - Hardened for acceptance criteria, priority, and ownership capture.
- `.github/PULL_REQUEST_TEMPLATE.md`
  - Hardened for risk + rollback + evidence context.
- `.github/ISSUE_TEMPLATE/config.yml`
  - Fixed to valid list-based contact links and tightened defaults (`blank_issues_enabled: false`).

### Tests and checks

- `tests/test_triage_templates.py`
  - Added isolated root-scoped validation tests.
  - Added strict failure behavior test for missing requirements.
  - Added auto-recovery write-defaults test.
- `tests/test_cli_help_lists_subcommands.py`
  - Keeps CLI help contract coverage for `triage-templates`.
- `scripts/check_day9_contribution_templates_contract.py`
  - Enforces Day 9 docs/report/contract references.

### Docs and artifacts

- `README.md`
  - Expanded Day 9 section with strict validation + write-defaults recovery command.
- `docs/index.md`
  - Expanded Day 9 quick action list with auto-recovery command.
- `docs/cli.md`
  - Expanded `triage-templates` reference with `--root` and `--write-defaults` semantics.
- `docs/artifacts/day9-triage-templates-sample.md`
  - Refreshed generated Day 9 template-health artifact sample.

## Validation checklist

- `python -m pytest -q tests/test_triage_templates.py tests/test_cli_help_lists_subcommands.py tests/test_contributor_funnel.py`
- `python scripts/check_day9_contribution_templates_contract.py`
- `python -m sdetkit triage-templates --format json --strict`
- `python -m sdetkit triage-templates --write-defaults --format json --strict`

## Artifacts

- `docs/artifacts/day9-triage-templates-sample.md`

## Rollback plan

1. Revert `src/sdetkit/triage_templates.py` to the previous token-checking implementation.
2. Revert `.github` template/config files to pre-Day-9 state.
3. Revert Day 9 docs/report updates and remove Day 9 contract checker if desired.

This document is the Day 9 artifact report for contribution-template triage hardening and recovery automation.
