# Lane — Optimization closeout lane

Lane closes with a major optimization upgrade that converts Lane expansion evidence into deterministic improvement loops.

## Why Lane matters

- Converts Lane expansion proof into optimization-first operating motion.
- Protects quality with owner accountability, command proof, and KPI guardrails.
- Produces a deterministic handoff from optimization outcomes into Lane reliability priorities.

## Required inputs (Lane)

- `docs/artifacts/expansion-closeout-pack/expansion-closeout-summary.json`
- `docs/artifacts/expansion-closeout-pack/expansion-delivery-board.md`

## Lane command lane

```bash
python -m sdetkit optimization-closeout --format json --strict
python -m sdetkit optimization-closeout --emit-pack-dir docs/artifacts/optimization-closeout-pack --format json --strict
python -m sdetkit optimization-closeout --execute --evidence-dir docs/artifacts/optimization-closeout-pack/evidence --format json --strict
python scripts/check_optimization_closeout_contract.py
```

## Optimization closeout contract

- Single owner + backup reviewer are assigned for Lane optimization lane execution and KPI follow-up.
- The Lane optimization lane references Lane expansion winners and misses with deterministic optimization loops.
- Every Lane section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Lane closeout records optimization learnings and Lane reliability priorities.

## Optimization quality checklist

- [ ] Includes optimization summary, bottleneck map, and rollback strategy
- [ ] Every section has owner, publish window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes optimization plan, bottleneck map, KPI scorecard, and execution log

## Lane delivery board

- [ ] Lane optimization plan draft committed
- [ ] Lane review notes captured with owner + backup
- [ ] Lane bottleneck map exported
- [ ] Lane KPI scorecard snapshot exported
- [ ] Lane reliability priorities drafted from Lane learnings

## Scoring model

Lane weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 35 points.
- Optimization contract lock + delivery board readiness: 15 points.
