# Cycle 47 — Reliability closeout lane

Cycle 47 closes with a major reliability upgrade that converts Cycle 46 optimization evidence into deterministic hardening loops.

## Why Cycle 47 matters

- Converts Cycle 46 optimization proof into reliability-first operating motion.
- Protects quality with owner accountability, command proof, and KPI guardrails.
- Produces a deterministic handoff from reliability outcomes into Cycle 48 execution priorities.

## Required inputs (Cycle 46)

- `docs/artifacts/optimization-closeout-pack/optimization-closeout-summary.json`
- `docs/artifacts/optimization-closeout-pack/optimization-delivery-board.md`

## Cycle 47 command lane

```bash
python -m sdetkit reliability-closeout --format json --strict
python -m sdetkit reliability-closeout --emit-pack-dir docs/artifacts/cycle47-reliability-closeout-pack --format json --strict
python -m sdetkit reliability-closeout --execute --evidence-dir docs/artifacts/cycle47-reliability-closeout-pack/evidence --format json --strict
python scripts/check_reliability_closeout_contract.py
```

## Reliability closeout contract

- Single owner + backup reviewer are assigned for Cycle 47 reliability lane execution and KPI follow-up.
- The Cycle 47 reliability lane references Cycle 46 optimization winners and misses with deterministic reliability loops.
- Every Cycle 47 section includes docs CTA, runnable command CTA, KPI target, and rollout guardrail.
- Cycle 47 closeout records reliability learnings and Cycle 48 execution priorities.

## Reliability quality checklist

- [ ] Includes reliability summary, incident map, and rollback strategy
- [ ] Every section has owner, publish window, KPI target, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes reliability plan, incident map, KPI scorecard, and execution log

## Cycle 47 delivery board

- [ ] Cycle 47 reliability plan draft committed
- [ ] Cycle 47 review notes captured with owner + backup
- [ ] Cycle 47 incident map exported
- [ ] Cycle 47 KPI scorecard snapshot exported
- [ ] Cycle 48 execution priorities drafted from Cycle 47 learnings

## Scoring model

Cycle 47 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Cycle 46 continuity and strict baseline carryover: 35 points.
- Reliability contract lock + delivery board readiness: 15 points.
