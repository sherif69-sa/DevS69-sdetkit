# Day 21 ultra upgrade report

## Day 21 big upgrade

Day 21 ships **weekly review #3** so teams can objectively track conversion improvements and external contributor response across Days 15-20.

## What shipped

- Extended `sdetkit weekly-review` to support `--week 3` (Day 15-20 shipped window).
- Added Day 21 growth-signal sample input for deterministic week-over-week deltas.
- Added Day 20/21 documentation entries in README and docs index.
- Added tests covering week-3 KPI behavior, growth-delta computation, and week-3 emitted closeout pack output.

## Validation commands

```bash
python -m pytest -q tests/test_weekly_review.py tests/test_cli_help_lists_subcommands.py
python -m sdetkit weekly-review --week 3 --format json --signals-file docs/artifacts/day21-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --strict
python -m sdetkit weekly-review --week 3 --format markdown --signals-file docs/artifacts/day21-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --output docs/artifacts/day21-weekly-review-sample.md
python -m sdetkit weekly-review --week 3 --emit-pack-dir docs/artifacts/day21-weekly-pack --signals-file docs/artifacts/day21-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --format json --strict
python scripts/check_day21_weekly_review_contract.py
```

## Closeout

Day 21 now provides a week-3 closeout lane that surfaces shipped coverage, KPI posture, and contributor/traffic deltas in one review payload.
