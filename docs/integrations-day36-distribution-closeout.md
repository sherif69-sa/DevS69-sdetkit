# Day 36 — Community distribution closeout

Day 36 closes the distribution lane by converting the Day 35 KPI story into channel-ready messaging, schedule commitments, and Day 37 experiments.

## Why Day 36 matters

- Converts KPI insights into public distribution execution.
- Protects consistency by defining owner, backup reviewer, and posting windows.
- Creates a direct handoff from distribution misses into Day 37 experiment backlog.

## Required inputs (Day 35)

- `docs/artifacts/day35-kpi-instrumentation-pack/day35-kpi-instrumentation-summary.json`
- `docs/artifacts/day35-kpi-instrumentation-pack/day35-delivery-board.md`

## Day 36 command lane

```bash
python -m sdetkit distribution-closeout --format json --strict
python -m sdetkit distribution-closeout --emit-pack-dir docs/artifacts/day36-distribution-closeout-pack --format json --strict
python -m sdetkit distribution-closeout --execute --evidence-dir docs/artifacts/day36-distribution-closeout-pack/evidence --format json --strict
python scripts/check_day36_distribution_closeout_contract.py
```

## Distribution contract

- Single owner + backup reviewer are assigned for distribution publishing.
- Primary channels include GitHub, LinkedIn, and community newsletter with explicit audience goal.
- Every post variant maps to one KPI from Day 35 with target delta and follow-up action.
- Day 36 report includes at least three Day 37 experiments seeded from distribution misses.

## Distribution quality checklist

- [ ] Includes at least three channel-specific message variants
- [ ] Every channel variant has CTA, KPI target, and owner
- [ ] Posting schedule includes exact date/time and reviewer
- [ ] Engagement deltas include baseline from Day 35 metrics
- [ ] Artifact pack includes launch plan, message kit, and experiment backlog

## Day 36 delivery board

- [ ] Day 36 launch plan committed
- [ ] Day 36 message kit reviewed with owner + backup
- [ ] Day 36 posting windows locked
- [ ] Day 37 experiment backlog seeded from channel misses
- [ ] Day 37 summary owner confirmed

## Scoring model

Day 36 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 35 continuity and strict baseline carryover: 35 points.
- Distribution contract lock + delivery board readiness: 15 points.
