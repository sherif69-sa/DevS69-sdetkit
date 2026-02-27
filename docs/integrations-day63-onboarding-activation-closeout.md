# Day 63 — Contributor onboarding activation closeout lane

Day 63 closes with a major onboarding activation upgrade that turns Day 62 community operations evidence into deterministic contributor activation, ownership handoffs, and roadmap voting execution.

## Why Day 63 matters

- Converts Day 62 community momentum into repeatable onboarding and mentor ownership loops.
- Protects onboarding outcomes with strict contract coverage, runnable commands, and rollback safety.
- Creates a deterministic handoff from Day 63 onboarding activation to Day 64 contributor pipeline acceleration.

## Required inputs (Day 62)

- `docs/artifacts/day62-community-program-closeout-pack/day62-community-program-closeout-summary.json`
- `docs/artifacts/day62-community-program-closeout-pack/day62-delivery-board.md`

## Day 63 command lane

```bash
python -m sdetkit day63-onboarding-activation-closeout --format json --strict
python -m sdetkit day63-onboarding-activation-closeout --emit-pack-dir docs/artifacts/day63-onboarding-activation-closeout-pack --format json --strict
python -m sdetkit day63-onboarding-activation-closeout --execute --evidence-dir docs/artifacts/day63-onboarding-activation-closeout-pack/evidence --format json --strict
python scripts/check_day63_onboarding_activation_closeout_contract.py
```

## Onboarding activation contract

- Single owner + backup reviewer are assigned for Day 63 onboarding activation execution and roadmap-voting facilitation.
- The Day 63 lane references Day 62 community-program outcomes, moderation guardrails, and KPI continuity evidence.
- Every Day 63 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 63 closeout records onboarding orientation flow, ownership handoff SOP, roadmap voting launch, and Day 64 pipeline priorities.

## Onboarding quality checklist

- [ ] Includes onboarding orientation path, mentor ownership model, and rollback trigger
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures activation conversion, mentor SLA, roadmap-vote participation, confidence, and recovery owner
- [ ] Artifact pack includes onboarding brief, orientation script, ownership matrix, roadmap-vote brief, and execution log

## Day 63 delivery board

- [ ] Day 63 onboarding launch brief committed
- [ ] Day 63 orientation script + ownership matrix published
- [ ] Day 63 roadmap voting brief exported
- [ ] Day 63 KPI scorecard snapshot exported
- [ ] Day 64 contributor pipeline priorities drafted from Day 63 learnings

## Scoring model

Day 63 weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 62 continuity and strict baseline carryover: 35 points.
- Onboarding activation contract lock + delivery board readiness: 15 points.
