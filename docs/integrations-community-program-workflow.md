# Community program setup workflow

Lane ships a major community-program upgrade that converts Lane kickoff evidence into a strict baseline for office-hours, participation, and moderation execution.

## Why Community Program Completion matters

- Converts Lane completion report evidence into repeatable community operations loops.
- Protects trust outcomes with ownership, command proof, and moderation rollback guardrails.
- Produces a deterministic handoff from Lane community setup into Lane onboarding activation.

## Required inputs (Lane)

- `docs/artifacts/platform-readiness-kickoff-completion-report-pack/platform-readiness-kickoff-completion-report-summary.json`
- `docs/artifacts/platform-readiness-kickoff-completion-report-pack/platform-readiness-kickoff-delivery-board.md`

## Community Program Completion command lane (legacy)

```bash
python -m sdetkit community-program-completion --format json --strict
python -m sdetkit community-program-completion --emit-pack-dir docs/artifacts/community-program-completion-pack --format json --strict
python -m sdetkit community-program-completion --execute --evidence-dir docs/artifacts/community-program-completion-pack/evidence --format json --strict
python scripts/check_community_program_completion_contract.py
```

## Community program execution contract

- Single owner + backup reviewer are assigned for Lane community office-hours execution and moderation safety.
- This lane references Lane platform readiness kickoff outcomes, trust guardrails, and KPI continuity evidence.
- Every Lane section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Lane completion report records office-hours cadence, participation rules, moderation SOPs, and Lane onboarding priorities.

## Community program quality checklist

- [ ] Includes office-hours calendar, participation policy, escalation flow, and rollback trigger
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures attendance target, response SLA, trust incidents, confidence, and recovery owner
- [ ] Artifact pack includes launch brief, participation policy, moderation runbook, and execution log

## Community Program Completion delivery board (legacy)

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
