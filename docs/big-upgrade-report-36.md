# Cycle 36 Big Upgrade Report

## What shipped

- Added Cycle 36 closeout command: `python -m sdetkit cycle36-distribution-closeout`.
- Added strict continuity checks that require Cycle 35 strict-pass and board integrity.
- Added Cycle 36 artifact outputs for distribution message kit, launch plan, experiment backlog, and validation commands.

## Validation

```bash
python -m pytest -q tests/test_day36_distribution_closeout.py tests/test_cli_help_lists_subcommands.py
python scripts/check_distribution_closeout_contract.py --skip-evidence
python -m sdetkit cycle36-distribution-closeout --format json --strict
```

## Cycle 37 handoff

Cycle 36 is closed with a distribution contract that feeds Cycle 37 experimentation using channel-level misses and KPI targets.
