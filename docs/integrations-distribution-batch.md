# Lane — Distribution batch #1

Lane publishes a coordinated distribution batch that operationalizes Lane experiment winners into high-signal channel execution.

## Why Lane matters

- Converts Lane learning into external distribution outcomes across multiple channels.
- Preserves quality by enforcing owner accountability, CTA integrity, and KPI targets.
- Creates a deterministic handoff from distribution outcomes into Lane playbook content priorities.

## Required inputs (Lane)

- `docs/artifacts/experiment-lane-pack/experiment-lane-summary.json`
- `docs/artifacts/experiment-lane-pack/delivery-board.md`

## Lane command lane

```bash
python -m sdetkit distribution-batch --format json --strict
python -m sdetkit distribution-batch --emit-pack-dir docs/artifacts/distribution-batch-pack --format json --strict
python -m sdetkit distribution-batch --execute --evidence-dir docs/artifacts/distribution-batch-pack/evidence --format json --strict
python scripts/check_distribution_batch_contract.py
```

## Distribution contract

- Single owner + backup reviewer are assigned for Lane posting execution and outcome logging.
- At least three coordinated channel posts are linked to Lane winners and mapped to audience segments.
- Every Lane post includes docs CTA, command CTA, and one measurable KPI target.
- Lane closeout records winners, misses, and Lane playbook-post priorities.

## Distribution quality checklist

- [ ] Includes at least three coordinated posts across distinct channels
- [ ] Every post has owner, scheduled window, and KPI target
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, and delta for each channel KPI
- [ ] Artifact pack includes channel plan, post copy, scorecard, and execution log

## Lane delivery board

- [ ] Lane channel plan committed
- [ ] Lane post copy reviewed with owner + backup
- [ ] Lane scheduling matrix exported
- [ ] Lane KPI scorecard snapshot exported
- [ ] Lane playbook post priorities drafted from Lane outcomes

## Scoring model

Lane weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 35 points.
- Distribution contract lock + delivery board readiness: 15 points.
