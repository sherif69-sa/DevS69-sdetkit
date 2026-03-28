# Cycle 37 Big Upgrade Report

## What shipped

- Added Cycle 37 closeout command: `python -m sdetkit cycle37-experiment-lane`.
- Added strict continuity checks that require Cycle 36 strict-pass and board integrity.
- Added Cycle 37 artifact outputs for experiment matrix, hypothesis brief, scorecard, decision log, and validation commands.

## Validation

```bash
python -m pytest -q tests/test_day37_experiment_lane.py tests/test_cli_help_lists_subcommands.py
python scripts/check_experiment_lane_contract.py --skip-evidence
python -m sdetkit cycle37-experiment-lane --format json --strict
```

## Cycle 38 handoff

Cycle 37 is closed with an experiment contract that turns validated winners into Cycle 38 distribution batch actions.
