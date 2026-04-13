# Adoption scorecard

This scorecard gives one compact maturity snapshot from existing governance artifacts:

- onboarding
- quality
- release
- ops

Each dimension is scored out of 25 (`0` or `25` currently), total score is out of 100.

## Generate scorecard

```bash
python scripts/adoption_scorecard.py --format json
```

Default inputs:

- `.sdetkit/out/golden-path-health.json`
- `.sdetkit/out/canonical-path-drift.json`
- `.sdetkit/out/legacy-command-analyzer.json`

Default output:

- `.sdetkit/out/adoption-scorecard.json`

## Output contract

- `schema_version`
- `score`
- `band` (`early`, `developing`, `strong`, `excellent`)
- `dimensions` (`onboarding`, `quality`, `release`, `ops`)
