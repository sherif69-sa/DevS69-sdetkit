# Contributor Activation Closeout lane (Legacy)

Lane closes with a major contributor activation upgrade that turns Lane docs-loop evidence into a deterministic contributor follow-through lane.

## Why Lane matters

- Converts Lane docs-loop wins into repeatable contributor activation motions.
- Protects quality with ownership, command proof, and KPI guardrails.
- Produces a deterministic handoff from Lane closeout into Lane planning.

## Required inputs (Lane)

- `docs/artifacts/docs-loop-closeout-pack/docs-loop-closeout-summary.json`
- `docs/artifacts/docs-loop-closeout-pack/docs-loop-delivery-board.md`

## Contributor Activation Closeout command lane

```bash
python -m sdetkit contributor-activation-closeout --format json --strict
python -m sdetkit contributor-activation-closeout --emit-pack-dir docs/artifacts/contributor-activation-closeout-pack --format json --strict
python -m sdetkit contributor-activation-closeout --execute --evidence-dir docs/artifacts/contributor-activation-closeout-pack/evidence --format json --strict
python scripts/check_contributor_activation_closeout_contract.py
```

## Contributor activation contract

- Single owner + backup reviewer are assigned for Lane contributor-activation execution and KPI follow-up.
- This lane references Lane docs-loop wins and misses with deterministic contributor follow-up loops.
- Every Lane section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Lane closeout records contributor-activation learnings and Lane prioritization inputs.

## Contributor activation quality checklist

- [ ] Includes wins/misses digest, activation experiments, and rollback strategy
- [ ] Every section has owner, review window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes contributor brief, contributor ladder, KPI scorecard, and execution log

## Lane delivery board

- [ ] Lane contributor brief committed
- [ ] Lane activation plan reviewed with owner + backup
- [ ] Lane contributor ladder exported
- [ ] Lane KPI scorecard snapshot exported
- [ ] Lane priorities drafted from Lane learnings

## Scoring model

Lane weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 35 points.
- Activation contract lock + delivery board readiness: 15 points.
