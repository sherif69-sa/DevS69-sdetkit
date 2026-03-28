# Community Program Closeout (legacy) — Community program setup closeout lane

Lane ships a major community-program upgrade that converts Lane kickoff evidence into a strict baseline for office-hours, participation, and moderation execution.

## Why Community Program Closeout matters

- Converts Lane closeout evidence into repeatable community operations loops.
- Protects trust outcomes with ownership, command proof, and moderation rollback guardrails.
- Produces a deterministic handoff from Lane community setup into Lane onboarding activation.

## Required inputs (Lane)

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

- Single owner + backup reviewer are assigned for Lane community office-hours execution and moderation safety.
- The Lane lane references Lane Phase-3 kickoff outcomes, trust guardrails, and KPI continuity evidence.
- Every Lane section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Lane closeout records office-hours cadence, participation rules, moderation SOPs, and Lane onboarding priorities.

## Community program quality checklist

- [ ] Includes office-hours calendar, participation policy, escalation flow, and rollback trigger
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures attendance target, response SLA, trust incidents, confidence, and recovery owner
- [ ] Artifact pack includes launch brief, participation policy, moderation runbook, and execution log

## Community Program Closeout delivery board (legacy)

- [ ] Lane community launch brief committed
- [ ] Lane office-hours cadence published
- [ ] Lane participation policy + moderation SOP exported
- [ ] Lane KPI scorecard snapshot exported
- [ ] Lane onboarding priorities drafted from Lane learnings

## Scoring model

Lane weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 35 points.
- Community program contract lock + delivery board readiness: 15 points.
