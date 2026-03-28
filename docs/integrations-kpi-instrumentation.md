# Day 35 — KPI instrumentation closeout

Day 35 closes the week with a hardened KPI operating loop that ties growth narrative to measurable thresholds and owners.

## Why Day 35 matters

- Converts production demo momentum into persistent weekly measurement.
- Eliminates attribution blind spots with explicit source-command mapping per KPI.
- Forces decisions by pairing every drift signal with a next-week action.

## Required inputs (Day 34)

- `docs/artifacts/demo-asset2-pack/demo-asset2-summary.json`
- `docs/artifacts/demo-asset2-pack/demo-asset2-delivery-board.md`

## Day 35 command lane

```bash
python -m sdetkit kpi-instrumentation --format json --strict
python -m sdetkit kpi-instrumentation --emit-pack-dir docs/artifacts/day35-kpi-instrumentation-pack --format json --strict
python -m sdetkit kpi-instrumentation --execute --evidence-dir docs/artifacts/day35-kpi-instrumentation-pack/evidence --format json --strict
python scripts/check_kpi_instrumentation_contract.py
```

## KPI instrumentation contract

- Single owner + backup reviewer are assigned for KPI instrumentation maintenance.
- Metric taxonomy includes acquisition, activation, retention, and reliability slices.
- Every KPI has source command, cadence, owner, and threshold fields documented.
- Day 35 report links KPI drift to at least three concrete next-week actions.

## KPI quality checklist

- [ ] Includes at least eight KPIs split across acquisition/activation/retention/reliability
- [ ] Every KPI row has source command and refresh cadence
- [ ] At least three threshold alerts are documented with owner + escalation action
- [ ] Weekly review delta compares current week vs prior week in percentages
- [ ] Artifact pack includes dashboard, alert policy, and narrative summary

## Day 35 delivery board

- [ ] Day 35 KPI dictionary committed
- [ ] Day 35 dashboard snapshot exported
- [ ] Day 35 alert policy reviewed with owner + backup
- [ ] Day 36 distribution message references KPI shifts
- [ ] Day 37 experiment backlog seeded from KPI misses

## Scoring model

Day 35 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 34 continuity and strict baseline carryover: 35 points.
- KPI contract lock + delivery board readiness: 15 points.
