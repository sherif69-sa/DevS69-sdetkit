# Cycle 4 Ultra Upgrade Report — Skills Expansion + Full Template Sweep

## Upgrade title

**Cycle 4 scale-up: run every built-in automation skill/template with one deterministic command**

## Problem statement

By Cycle 3, teams had proof artifacts and governance outputs, but they still had to invoke each automation template individually.

For Cycle 4, operators needed a single command that executes all built-in skills/templates and stores artifacts in a predictable layout.

## Implementation scope

### Files changed

- `src/sdetkit/agent/cli.py`
  - Added `sdetkit agent templates run-all` command.
  - Added `--output-dir` option for base output path.
  - Added aggregate JSON payload with per-template run records.
- `tests/test_agent_templates_cli.py`
  - Added coverage for `templates run-all` execution contract and output files.
- `docs/cli.md`
  - Added `templates run-all` command reference.
- `README.md`
  - Added Cycle 4 ultra section for skills expansion and closeout checks.
- `docs/index.md`
  - Added Cycle 4 ultra docs entry and quick-jump link.
- `docs/artifacts/cycle4-skills-sample.md`
  - Added skills/template inventory artifact for handoff traceability.
- `scripts/check_day4_skills_contract.py`
  - Added contract check to validate Cycle 4 docs + links.

## Validation checklist

- `python -m pytest -q tests/test_agent_templates_cli.py`
- `python scripts/check_day4_skills_contract.py`

## Artifact

This document is the Cycle 4 artifact for skills/template expansion and operational handoff.

## Rollback plan

1. Remove `run-all` parser/dispatch from `src/sdetkit/agent/cli.py`.
2. Revert Cycle 4 documentation blocks and links.
3. Remove Cycle 4 artifact/report/contract-check files.

Rollback risk is low because this is additive command + docs surface.
