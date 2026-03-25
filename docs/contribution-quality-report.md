# Day 17 ultra upgrade report

## Day 17 big upgrade

Day 17 adds a unified **quality + contribution delta evidence pack** so maintainers can compare week-over-week delivery KPIs and growth signals in one command.

## What shipped

- New CLI command: `sdetkit quality-contribution-delta` with velocity score, stability score, recommendation engine, and strict delta gates.
- New contribution-quality sample artifact and expanded emitted pack under `docs/artifacts/contribution-quality-report-pack` (summary, scorecard, action plan, remediation checklist).
- New contract checker: `scripts/check_day17_quality_contribution_delta_contract.py`.
- CLI dispatcher and help coverage updated to include `quality-contribution-delta`.

## Validation commands

```bash
python -m sdetkit contribution-quality-report --current-signals-file docs/artifacts/contribution-quality-growth-signals.json --previous-signals-file docs/artifacts/growth-signals-baseline.json --format json --strict
python -m sdetkit contribution-quality-report --current-signals-file docs/artifacts/contribution-quality-growth-signals.json --previous-signals-file docs/artifacts/growth-signals-baseline.json --emit-pack-dir docs/artifacts/contribution-quality-report-pack --format json --strict
python scripts/check_day17_quality_contribution_delta_contract.py
```

## Closeout

Day 17 now has one deterministic evidence path for week-over-week quality and contribution deltas.
