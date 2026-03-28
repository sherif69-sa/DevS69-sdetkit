# KPI audit (Lane)

Lane closes the conversion sprint by comparing baseline vs current KPI performance and publishing corrective actions.

## Who should run Lane

- Maintainers validating weekly growth outcomes from Cycles 22-26.
- DevRel/community operators tracking traffic-to-contribution conversion.
- Engineering managers proving roadmap execution impact.

## KPI contract

A Lane pass requires side-by-side baseline and current snapshots for:

- `stars_per_week`
- `readme_ctr_percent`
- `discussions_per_week`
- `external_prs_per_week`

## Metric baseline and current snapshot

- Baseline path: `docs/artifacts/kpi-audit-pack/kpi-baseline.json`
- Current path: `docs/artifacts/kpi-audit-pack/kpi-current.json`
- Every metric must be numeric and non-negative.

## Launch checklist

```bash
python -m sdetkit kpi-audit --format json --strict
python -m sdetkit kpi-audit --emit-pack-dir docs/artifacts/kpi-audit-pack --format json --strict
python -m sdetkit kpi-audit --execute --evidence-dir docs/artifacts/kpi-audit-pack/evidence --format json --strict
python scripts/check_kpi_audit_contract.py
```

## KPI scoring model

Lane computes weighted readiness score (0-100):

- Docs contract + command lane completeness: 45 points.
- Discoverability links in README/docs index: 20 points.
- Top-10 roadmap and KPI vocabulary alignment: 15 points.
- Baseline/current metric data validity: 20 points.

## Execution evidence mode

`--execute` runs deterministic Lane checks and writes logs to `--evidence-dir` for final closeout review.
