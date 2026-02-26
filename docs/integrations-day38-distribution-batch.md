# Day 38 — Distribution batch #1

Day 38 publishes a coordinated distribution batch that operationalizes Day 37 experiment winners into high-signal channel execution.

## Why Day 38 matters

- Converts Day 37 learning into external distribution outcomes across multiple channels.
- Preserves quality by enforcing owner accountability, CTA integrity, and KPI targets.
- Creates a deterministic handoff from distribution outcomes into Day 39 playbook content priorities.

## Required inputs (Day 37)

- `docs/artifacts/day37-experiment-lane-pack/day37-experiment-lane-summary.json`
- `docs/artifacts/day37-experiment-lane-pack/day37-delivery-board.md`

## Day 38 command lane

```bash
python -m sdetkit day38-distribution-batch --format json --strict
python -m sdetkit day38-distribution-batch --emit-pack-dir docs/artifacts/day38-distribution-batch-pack --format json --strict
python -m sdetkit day38-distribution-batch --execute --evidence-dir docs/artifacts/day38-distribution-batch-pack/evidence --format json --strict
python scripts/check_day38_distribution_batch_contract.py
```

## Distribution contract

- Single owner + backup reviewer are assigned for Day 38 posting execution and outcome logging.
- At least three coordinated channel posts are linked to Day 37 winners and mapped to audience segments.
- Every Day 38 post includes docs CTA, command CTA, and one measurable KPI target.
- Day 38 closeout records winners, misses, and Day 39 playbook-post priorities.

## Distribution quality checklist

- [ ] Includes at least three coordinated posts across distinct channels
- [ ] Every post has owner, scheduled window, and KPI target
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, and delta for each channel KPI
- [ ] Artifact pack includes channel plan, post copy, scorecard, and execution log

## Day 38 delivery board

- [ ] Day 38 channel plan committed
- [ ] Day 38 post copy reviewed with owner + backup
- [ ] Day 38 scheduling matrix exported
- [ ] Day 38 KPI scorecard snapshot exported
- [ ] Day 39 playbook post priorities drafted from Day 38 outcomes

## Scoring model

Day 38 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 37 continuity and strict baseline carryover: 35 points.
- Distribution contract lock + delivery board readiness: 15 points.
