# Optimization foundation workflow

Optimization Completion Foundation closes the lane with a major optimization upgrade that converts Lane expansion outcomes into deterministic remediation loops.

## Why Optimization Completion Foundation matters

- Turns Lane expansion proof into remediation-first operating motion.
- Locks quality controls while increasing repeatability and throughput.
- Produces a deterministic handoff into Lane acceleration priorities.

## Required inputs (Lane)

- `docs/artifacts/expansion-automation-pack/expansion-automation-summary.json`
- `docs/artifacts/expansion-automation-pack/delivery-board.md`

## Optimization Completion Foundation command lane

```bash
python -m sdetkit optimization-completion-foundation --format json --strict
python -m sdetkit optimization-completion-foundation --emit-pack-dir docs/artifacts/optimization-completion-foundation-pack --format json --strict
python -m sdetkit optimization-completion-foundation --execute --evidence-dir docs/artifacts/optimization-completion-foundation-pack/evidence --format json --strict
python scripts/check_optimization_completion_contract.py
```

## Optimization completion report contract

- Single owner + backup reviewer are assigned for Optimization Completion Foundation optimization lane execution and KPI follow-up.
- The Optimization Completion Foundation optimization lane references Lane expansion winners and misses with deterministic remediation loops.
- Every Optimization Completion Foundation section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Optimization Completion Foundation completion report records optimization learnings and Lane acceleration priorities.

## Optimization quality checklist

- [ ] Includes optimization summary, remediation matrix, and rollback strategy
- [ ] Every section has owner, publish window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes optimization plan, remediation matrix, KPI scorecard, and execution log

## Optimization Completion Foundation delivery board

- [ ] Optimization Completion Foundation optimization plan draft committed
- [ ] Optimization Completion Foundation review notes captured with owner + backup
- [ ] Optimization Completion Foundation remediation matrix exported
- [ ] Optimization Completion Foundation KPI scorecard snapshot exported
- [ ] Lane acceleration priorities drafted from Optimization Completion Foundation learnings

## Scoring model

Optimization Completion Foundation weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 35 points.
- Optimization execution contract lock + delivery board readiness: 15 points.
