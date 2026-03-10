# Weekly review #4 (Day 28)

Day 28 closes the weekly growth loop by consolidating Day 25-27 outcomes into wins, misses, and corrective actions.

## Who should run Day 28

- Maintainers preparing Phase-1 closeout and Day 29 hardening priorities.
- DevRel/community operators validating that activation efforts converted to contributions.
- Engineering managers requiring an auditable weekly checkpoint before handoff.

## Inputs from Days 25-27

- Day 25: `docs/artifacts/day25-community-pack/day25-community-summary.json`
- Day 26: `docs/artifacts/day26-external-contribution-pack/day26-external-contribution-summary.json`
- Day 27: `docs/artifacts/day27-kpi-pack/day27-kpi-summary.json`

## Closeout checklist

```bash
python -m sdetkit day28-weekly-review --format json --strict
python -m sdetkit day28-weekly-review --emit-pack-dir docs/artifacts/day28-weekly-pack --format json --strict
python -m sdetkit day28-weekly-review --execute --evidence-dir docs/artifacts/day28-weekly-pack/evidence --format json --strict
python scripts/check_day28_weekly_review_contract.py
```

## Scoring model

Day 28 weighted score (0-100):

- Docs contract + command lane completeness: 40 points.
- Discoverability links in README/docs index: 20 points.
- Roadmap alignment and closeout language quality: 15 points.
- Input artifact availability from Days 25-27: 25 points.

## Evidence mode

`--execute` runs deterministic checks and captures command logs in `--evidence-dir`.
