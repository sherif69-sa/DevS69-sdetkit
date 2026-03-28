# Lane — Community distribution closeout

Lane closes the distribution lane by converting the Lane KPI story into channel-ready messaging, schedule commitments, and Lane experiments.

## Why Lane matters

- Converts KPI insights into public distribution execution.
- Protects consistency by defining owner, backup reviewer, and posting windows.
- Creates a direct handoff from distribution misses into Lane experiment backlog.

## Required inputs (Lane)

- `docs/artifacts/kpi-instrumentation-pack/kpi-instrumentation-summary.json`
- `docs/artifacts/kpi-instrumentation-pack/delivery-board.md`

## Lane command lane

```bash
python -m sdetkit distribution-closeout --format json --strict
python -m sdetkit distribution-closeout --emit-pack-dir docs/artifacts/distribution-closeout-pack --format json --strict
python -m sdetkit distribution-closeout --execute --evidence-dir docs/artifacts/distribution-closeout-pack/evidence --format json --strict
python scripts/check_distribution_closeout_contract.py
```

## Distribution contract

- Single owner + backup reviewer are assigned for distribution publishing.
- Primary channels include GitHub, LinkedIn, and community newsletter with explicit audience goal.
- Every post variant maps to one KPI from Lane with target delta and follow-up action.
- Lane report includes at least three Lane experiments seeded from distribution misses.

## Distribution quality checklist

- [ ] Includes at least three channel-specific message variants
- [ ] Every channel variant has CTA, KPI target, and owner
- [ ] Posting schedule includes exact date/time and reviewer
- [ ] Engagement deltas include baseline from Lane metrics
- [ ] Artifact pack includes launch plan, message kit, and experiment backlog

## Lane delivery board

- [ ] Lane launch plan committed
- [ ] Lane message kit reviewed with owner + backup
- [ ] Lane posting windows locked
- [ ] Lane experiment backlog seeded from channel misses
- [ ] Lane summary owner confirmed

## Scoring model

Lane weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 35 points.
- Distribution contract lock + delivery board readiness: 15 points.
