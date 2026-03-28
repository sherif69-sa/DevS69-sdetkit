# Community Program Closeout (legacy) — Community program setup closeout lane

Cycle 62 ships a major community-program upgrade that converts Cycle 61 kickoff evidence into a strict baseline for office-hours, participation, and moderation execution.

## Why Community Program Closeout matters

- Converts Cycle 61 closeout evidence into repeatable community operations loops.
- Protects trust outcomes with ownership, command proof, and moderation rollback guardrails.
- Produces a deterministic handoff from Cycle 62 community setup into Cycle 63 onboarding activation.

## Required inputs (Cycle 61)

- `docs/artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-closeout-summary.json`
- `docs/artifacts/phase3-kickoff-closeout-pack/phase3-kickoff-delivery-board.md`

## Community Program Closeout command lane (legacy)

```bash
python -m sdetkit community-program-closeout --format json --strict
python -m sdetkit community-program-closeout --emit-pack-dir docs/artifacts/community-program-closeout-pack --format json --strict
python -m sdetkit community-program-closeout --execute --evidence-dir docs/artifacts/community-program-closeout-pack/evidence --format json --strict
python scripts/check_community_program_closeout_contract.py
```

## Community program execution contract

- Single owner + backup reviewer are assigned for Cycle 62 community office-hours execution and moderation safety.
- The Cycle 62 lane references Cycle 61 Phase-3 kickoff outcomes, trust guardrails, and KPI continuity evidence.
- Every Cycle 62 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Cycle 62 closeout records office-hours cadence, participation rules, moderation SOPs, and Cycle 63 onboarding priorities.

## Community program quality checklist

- [ ] Includes office-hours calendar, participation policy, escalation flow, and rollback trigger
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures attendance target, response SLA, trust incidents, confidence, and recovery owner
- [ ] Artifact pack includes launch brief, participation policy, moderation runbook, and execution log

## Community Program Closeout delivery board (legacy)

- [ ] Cycle 62 community launch brief committed
- [ ] Cycle 62 office-hours cadence published
- [ ] Cycle 62 participation policy + moderation SOP exported
- [ ] Cycle 62 KPI scorecard snapshot exported
- [ ] Cycle 63 onboarding priorities drafted from Cycle 62 learnings

## Scoring model

Cycle 62 weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Cycle 61 continuity and strict baseline carryover: 35 points.
- Community program contract lock + delivery board readiness: 15 points.
