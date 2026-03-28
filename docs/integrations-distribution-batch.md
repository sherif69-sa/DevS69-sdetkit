# Cycle 38 — Distribution batch #1

Cycle 38 publishes a coordinated distribution batch that operationalizes Cycle 37 experiment winners into high-signal channel execution.

## Why Cycle 38 matters

- Converts Cycle 37 learning into external distribution outcomes across multiple channels.
- Preserves quality by enforcing owner accountability, CTA integrity, and KPI targets.
- Creates a deterministic handoff from distribution outcomes into Cycle 39 playbook content priorities.

## Required inputs (Cycle 37)

- `docs/artifacts/experiment-lane-pack/experiment-lane-summary.json`
- `docs/artifacts/experiment-lane-pack/delivery-board.md`

## Cycle 38 command lane

```bash
python -m sdetkit distribution-batch --format json --strict
python -m sdetkit distribution-batch --emit-pack-dir docs/artifacts/distribution-batch-pack --format json --strict
python -m sdetkit distribution-batch --execute --evidence-dir docs/artifacts/distribution-batch-pack/evidence --format json --strict
python scripts/check_distribution_batch_contract.py
```

## Distribution contract

- Single owner + backup reviewer are assigned for Cycle 38 posting execution and outcome logging.
- At least three coordinated channel posts are linked to Cycle 37 winners and mapped to audience segments.
- Every Cycle 38 post includes docs CTA, command CTA, and one measurable KPI target.
- Cycle 38 closeout records winners, misses, and Cycle 39 playbook-post priorities.

## Distribution quality checklist

- [ ] Includes at least three coordinated posts across distinct channels
- [ ] Every post has owner, scheduled window, and KPI target
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, and delta for each channel KPI
- [ ] Artifact pack includes channel plan, post copy, scorecard, and execution log

## Cycle 38 delivery board

- [ ] Cycle 38 channel plan committed
- [ ] Cycle 38 post copy reviewed with owner + backup
- [ ] Cycle 38 scheduling matrix exported
- [ ] Cycle 38 KPI scorecard snapshot exported
- [ ] Cycle 39 playbook post priorities drafted from Cycle 38 outcomes

## Scoring model

Cycle 38 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Cycle 37 continuity and strict baseline carryover: 35 points.
- Distribution contract lock + delivery board readiness: 15 points.
