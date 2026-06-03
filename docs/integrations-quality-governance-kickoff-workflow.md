# Quality governance kickoff workflow

Lane ships a major Phase-3 kickoff upgrade that converts Lane wrap evidence into a strict baseline for ecosystem + trust execution.

## Why Phase3 Kickoff Closeout matters

- Converts Lane completion report evidence into repeatable Phase-3 execution loops.
- Protects trust outcomes with ownership, command proof, and KPI rollback guardrails.
- Produces a deterministic handoff from Lane kickoff into Lane community program setup.

## Required inputs (Lane)

- `docs/artifacts/release-readiness-wrap-handoff-completion-report-pack/release-readiness-wrap-handoff-completion-report-summary.json`
- `docs/artifacts/release-readiness-wrap-handoff-completion-report-pack/phase2-wrap-handoff-delivery-board.md`

## Phase3 Kickoff Closeout command lane (legacy)

```bash
python -m sdetkit platform-readiness-kickoff-completion-report --format json --strict
python -m sdetkit platform-readiness-kickoff-completion-report --emit-pack-dir docs/artifacts/platform-readiness-kickoff-completion-report-pack --format json --strict
python -m sdetkit platform-readiness-kickoff-completion-report --execute --evidence-dir docs/artifacts/platform-readiness-kickoff-completion-report-pack/evidence --format json --strict
python scripts/check_phase3_kickoff_closeout_contract.py
```

## Phase-3 kickoff execution contract

- Single owner + backup reviewer are assigned for Lane Phase-3 kickoff execution and trust-signal triage.
- This lane references Lane Phase-2 wrap outcomes, risks, and KPI continuity evidence.
- Every Lane section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Lane completion report records Phase-3 baseline activation, trust KPI owners, and Lane community program priorities.

## Phase-3 kickoff quality checklist

- [ ] Includes baseline snapshot, owner map, KPI guardrails, and rollback strategy
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each trust KPI
- [ ] Artifact pack includes kickoff brief, trust ledger, KPI scorecard, and execution log

## Phase3 Kickoff Closeout delivery board (legacy)

- [ ] Lane Phase-3 kickoff brief committed
- [ ] Lane kickoff reviewed with owner + backup
- [ ] Lane trust ledger exported
- [ ] Lane KPI scorecard snapshot exported
- [ ] Lane community program priorities drafted from Lane learnings

## Scoring model

Lane weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 35 points.
- Phase-3 kickoff contract lock + delivery board readiness: 15 points.
