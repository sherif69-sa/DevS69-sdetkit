# Cycle 36 — Community distribution closeout

Cycle 36 closes the distribution lane by converting the Cycle 35 KPI story into channel-ready messaging, schedule commitments, and Cycle 37 experiments.

## Why Cycle 36 matters

- Converts KPI insights into public distribution execution.
- Protects consistency by defining owner, backup reviewer, and posting windows.
- Creates a direct handoff from distribution misses into Cycle 37 experiment backlog.

## Required inputs (Cycle 35)

- `docs/artifacts/kpi-instrumentation-pack/kpi-instrumentation-summary.json`
- `docs/artifacts/kpi-instrumentation-pack/delivery-board.md`

## Cycle 36 command lane

```bash
python -m sdetkit distribution-closeout --format json --strict
python -m sdetkit distribution-closeout --emit-pack-dir docs/artifacts/distribution-closeout-pack --format json --strict
python -m sdetkit distribution-closeout --execute --evidence-dir docs/artifacts/distribution-closeout-pack/evidence --format json --strict
python scripts/check_distribution_closeout_contract.py
```

## Distribution contract

- Single owner + backup reviewer are assigned for distribution publishing.
- Primary channels include GitHub, LinkedIn, and community newsletter with explicit audience goal.
- Every post variant maps to one KPI from Cycle 35 with target delta and follow-up action.
- Cycle 36 report includes at least three Cycle 37 experiments seeded from distribution misses.

## Distribution quality checklist

- [ ] Includes at least three channel-specific message variants
- [ ] Every channel variant has CTA, KPI target, and owner
- [ ] Posting schedule includes exact date/time and reviewer
- [ ] Engagement deltas include baseline from Cycle 35 metrics
- [ ] Artifact pack includes launch plan, message kit, and experiment backlog

## Cycle 36 delivery board

- [ ] Cycle 36 launch plan committed
- [ ] Cycle 36 message kit reviewed with owner + backup
- [ ] Cycle 36 posting windows locked
- [ ] Cycle 37 experiment backlog seeded from channel misses
- [ ] Cycle 37 summary owner confirmed

## Scoring model

Cycle 36 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Cycle 35 continuity and strict baseline carryover: 35 points.
- Distribution contract lock + delivery board readiness: 15 points.
