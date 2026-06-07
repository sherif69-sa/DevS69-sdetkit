# Documentation governance workflow

Lane closes with a major docs loop optimization upgrade that converts Lane narrative evidence into deterministic cross-link execution across examples, playbooks, and CLI docs.

## Why Lane matters

- Converts Lane narrative proof into a durable docs-loop optimization discipline.
- Protects quality with owner accountability, command proof, and KPI guardrails.
- Produces a deterministic handoff from Lane docs-loop upgrades into Lane re-engagement execution.

## Required inputs (Lane)

- `docs/artifacts/narrative-completion-pack/narrative-completion-summary.json`
- `docs/artifacts/narrative-completion-pack/narrative-delivery-board.md`

## Docs Loop Completion command lane

```bash
python -m sdetkit docs-loop-completion --format json --strict
python -m sdetkit docs-loop-completion --emit-pack-dir docs/artifacts/docs-loop-completion-pack --format json --strict
python -m sdetkit docs-loop-completion --execute --evidence-dir docs/artifacts/docs-loop-completion-pack/evidence --format json --strict
python scripts/check_docs_loop_completion_contract.py
```

## Docs loop optimization contract

- Single owner + backup reviewer are assigned for Lane docs-loop execution and KPI follow-up.
- The Lane docs-loop lane references Lane narrative winners and misses with deterministic cross-link remediation loops.
- Every Lane section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Lane completion report records docs-loop learnings and Lane re-engagement priorities.

## Docs loop quality checklist

- [ ] Includes wins/misses digest, proof snippet draft, and rollback strategy
- [ ] Every section has owner, review window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes docs-loop brief, cross-link map, KPI scorecard, and execution log

## Lane delivery board

- [ ] Lane docs-loop brief committed
- [ ] Lane docs-loop plan reviewed with owner + backup
- [ ] Lane cross-link map exported
- [ ] Lane KPI scorecard snapshot exported
- [ ] Lane re-engagement priorities drafted from Lane learnings

## Scoring model

Lane weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 35 points.
- Docs-loop contract lock + delivery board readiness: 15 points.
