# Onboarding Activation Closeout (legacy) — Contributor onboarding activation closeout lane

Lane closes with a major onboarding activation upgrade that turns Lane community operations evidence into deterministic contributor activation, ownership handoffs, and roadmap voting execution.

## Why Onboarding Activation Closeout matters

- Converts Lane community momentum into repeatable onboarding and mentor ownership loops.
- Protects onboarding outcomes with strict contract coverage, runnable commands, and rollback safety.
- Creates a deterministic handoff from Lane onboarding activation to Lane contributor pipeline acceleration.

## Required inputs (Lane)

- `docs/artifacts/community-program-closeout-pack/community-program-closeout-summary.json`
- `docs/artifacts/community-program-closeout-pack/community-program-delivery-board.md`

## Onboarding Activation Closeout command lane (legacy)

```bash
python -m sdetkit onboarding-activation-closeout --format json --strict
python -m sdetkit onboarding-activation-closeout --emit-pack-dir docs/artifacts/onboarding-activation-closeout-pack --format json --strict
python -m sdetkit onboarding-activation-closeout --execute --evidence-dir docs/artifacts/onboarding-activation-closeout-pack/evidence --format json --strict
python scripts/check_onboarding_activation_closeout_contract_63.py
```

## Onboarding activation contract

- Single owner + backup reviewer are assigned for Lane onboarding activation execution and roadmap-voting facilitation.
- This lane references Lane community-program outcomes, moderation guardrails, and KPI continuity evidence.
- Every Lane section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Lane closeout records onboarding orientation flow, ownership handoff SOP, roadmap voting launch, and Lane pipeline priorities.

## Onboarding quality checklist

- [ ] Includes onboarding orientation path, mentor ownership model, and rollback trigger
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures activation conversion, mentor SLA, roadmap-vote participation, confidence, and recovery owner
- [ ] Artifact pack includes onboarding brief, orientation script, ownership matrix, roadmap-vote brief, and execution log

## Onboarding Activation Closeout delivery board (legacy)

- [ ] Lane onboarding launch brief committed
- [ ] Lane orientation script + ownership matrix published
- [ ] Lane roadmap voting brief exported
- [ ] Lane KPI scorecard snapshot exported
- [ ] Lane contributor pipeline priorities drafted from Lane learnings

## Scoring model

Lane weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 35 points.
- Onboarding activation contract lock + delivery board readiness: 15 points.
