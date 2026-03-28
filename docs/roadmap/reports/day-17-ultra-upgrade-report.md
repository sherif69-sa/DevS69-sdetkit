# Cycle 17 ultra upgrade report

## Cycle 17 big upgrade

Cycle 17 adds a unified **quality + contribution delta evidence pack** so maintainers can compare week-over-week delivery KPIs and growth signals in one command.

## What shipped

- New CLI command: `sdetkit quality-contribution-delta` with velocity score, stability score, recommendation engine, and strict delta gates.
- New Cycle 17 sample artifact and expanded emitted pack under `docs/artifacts/contribution-quality-report-pack` (summary, scorecard, action plan, remediation checklist).
- New contract checker: `scripts/check_day17_quality_contribution_delta_contract.py`.
- CLI dispatcher and help coverage updated to include `quality-contribution-delta`.

## Validation commands

```bash
python -m sdetkit quality-contribution-delta --current-signals-file docs/artifacts/cycle17-growth-signals.json --previous-signals-file docs/artifacts/cycle14-growth-signals.json --format json --strict
python -m sdetkit quality-contribution-delta --current-signals-file docs/artifacts/cycle17-growth-signals.json --previous-signals-file docs/artifacts/cycle14-growth-signals.json --emit-pack-dir docs/artifacts/contribution-quality-report-pack --format json --strict
python scripts/check_day17_quality_contribution_delta_contract.py
```

## Closeout

Cycle 17 now has one deterministic evidence path for week-over-week quality and contribution deltas.
