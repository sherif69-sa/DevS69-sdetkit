# Weekly Review Closeout (legacy) — Weekly review #9 closeout lane

> Legacy alias: `weekly-review-closeout-2` remains supported; prefer `weekly-review-closeout` in active usage.

Cycle 65 closes with a major weekly review upgrade that converts Cycle 64 integration execution evidence into strict KPI governance and a deterministic Cycle 66 handoff.

## Why Weekly Review Closeout matters

- Consolidates Cycle 64 integration expansion signals into a high-confidence weekly KPI baseline.
- Protects momentum with strict review contract coverage, runnable commands, and rollback safeguards.
- Creates a deterministic handoff from Cycle 65 weekly review into Cycle 66 integration expansion #2.

## Required inputs (Cycle 64)

- `docs/artifacts/integration-expansion-closeout-pack/integration-expansion-closeout-summary.json`
- `docs/artifacts/integration-expansion-closeout-pack/integration-expansion-delivery-board.md`
- `.github/workflows/cycle64-advanced-github-actions-reference.yml`

## Weekly Review Closeout command lane (legacy)

```bash
python -m sdetkit weekly-review-closeout --format json --strict
python -m sdetkit weekly-review-closeout --emit-pack-dir docs/artifacts/weekly-review-closeout-2-pack --format json --strict
python -m sdetkit weekly-review-closeout --execute --evidence-dir docs/artifacts/weekly-review-closeout-2-pack/evidence --format json --strict
python scripts/check_weekly_review_closeout_contract_2.py
```

## Weekly review contract

- Single owner + backup reviewer are assigned for Cycle 65 weekly review scoring, risk triage, and handoff signoff.
- The Cycle 65 lane references Cycle 64 integration evidence, delivery board completion, and strict baseline continuity.
- Every Cycle 65 section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Cycle 65 closeout records weekly KPI deltas, governance decisions, and Cycle 66 integration expansion priorities.

## Weekly review quality checklist

- [ ] Includes KPI baseline deltas, confidence band, and anomaly narrative
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures pass-rate trend, reliability incidents, contributor signal quality, and recovery owner
- [ ] Artifact pack includes weekly brief, KPI dashboard, decision register, risk ledger, and execution log

## Weekly Review Closeout delivery board (legacy)

- [ ] Cycle 65 weekly brief committed
- [ ] Cycle 65 KPI dashboard snapshot exported
- [ ] Cycle 65 governance decision register published
- [ ] Cycle 65 risk and recovery ledger exported
- [ ] Cycle 66 integration expansion priorities drafted from Cycle 65 review

## Scoring model

Cycle 65 weighted score (0-100):

- Contract + command lane completeness: 25 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Cycle 64 continuity and strict baseline carryover: 30 points.
- Weekly review quality + governance handoff: 25 points.
