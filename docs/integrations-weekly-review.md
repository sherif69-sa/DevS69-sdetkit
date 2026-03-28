# Weekly review #4 (Cycle 28)

Cycle 28 closes the weekly growth loop by consolidating Cycle 25-27 outcomes into wins, misses, and corrective actions.

## Who should run Cycle 28

- Maintainers preparing Phase-1 closeout and Cycle 29 hardening priorities.
- DevRel/community operators validating that activation efforts converted to contributions.
- Engineering managers requiring an auditable weekly checkpoint before handoff.

## Inputs from Cycles 25-27

- Cycle 25: `docs/artifacts/community-activation-pack/community-activation-summary.json`
- External contribution: `docs/artifacts/external-contribution-pack/external-contribution-summary.json`
- Cycle 27: `docs/artifacts/kpi-audit-pack/kpi-audit-summary.json`

## Closeout checklist

```bash
python -m sdetkit weekly-review --format json --strict
python -m sdetkit weekly-review --emit-pack-dir docs/artifacts/weekly-review-pack --format json --strict
python -m sdetkit weekly-review --execute --evidence-dir docs/artifacts/weekly-review-pack/evidence --format json --strict
python scripts/check_weekly_review_contract.py
```

## Scoring model

Cycle 28 weighted score (0-100):

- Docs contract + command lane completeness: 40 points.
- Discoverability links in README/docs index: 20 points.
- Roadmap alignment and closeout language quality: 15 points.
- Input artifact availability from Cycles 25-27: 25 points.

## Evidence mode

`--execute` runs deterministic checks and captures command logs in `--evidence-dir`.
