# Scale closeout lane

Scale closeout converts acceleration evidence into deterministic scale execution loops.

## Why this lane matters

- Converts acceleration proof into a scale-first operating motion.
- Protects quality with owner accountability, command proof, and KPI guardrails.
- Produces a deterministic handoff from scale outcomes into expansion priorities.

## Required inputs (acceleration closeout)

- `docs/artifacts/acceleration-closeout-pack/acceleration-closeout-summary.json`
- `docs/artifacts/acceleration-closeout-pack/delivery-board.md`

## Command lane

```bash
python -m sdetkit scale-closeout --format json --strict
python -m sdetkit scale-closeout --emit-pack-dir docs/artifacts/scale-closeout-pack --format json --strict
python -m sdetkit scale-closeout --execute --evidence-dir docs/artifacts/scale-closeout-pack/evidence --format json --strict
python scripts/check_scale_closeout_contract.py
```

## Scale closeout contract

- Single owner + backup reviewer are assigned for the scale lane execution and KPI follow-up.
- The scale lane references acceleration winners and misses with deterministic growth loops.
- Every section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Scale closeout records learnings and expansion priorities.

## Scale quality checklist

- [ ] Includes scale summary, growth matrix, and rollback strategy
- [ ] Every section has owner, publish window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes scale plan, growth matrix, KPI scorecard, and execution log

## Delivery board

- [ ] Scale plan draft committed
- [ ] Review notes captured with owner + backup
- [ ] Growth matrix exported
- [ ] KPI scorecard snapshot exported
- [ ] Expansion priorities drafted from learnings

## Scoring model

Weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Scale continuity and strict baseline carryover: 35 points.
- Scale contract lock + delivery board readiness: 15 points.
