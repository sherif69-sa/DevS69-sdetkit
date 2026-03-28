# Weekly Review Closeout (legacy) — Weekly review #9 closeout lane

> Legacy alias: `weekly-review-closeout-2` remains supported; prefer `weekly-review-closeout` in active usage.

Lane closes with a major weekly review upgrade that converts Lane integration execution evidence into strict KPI governance and a deterministic Lane handoff.

## Why Weekly Review Closeout matters

- Consolidates Lane integration expansion signals into a high-confidence weekly KPI baseline.
- Protects momentum with strict review contract coverage, runnable commands, and rollback safeguards.
- Creates a deterministic handoff from Lane weekly review into Lane integration expansion #2.

## Required inputs (Lane)

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

- Single owner + backup reviewer are assigned for Lane weekly review scoring, risk triage, and handoff signoff.
- The Lane lane references Lane integration evidence, delivery board completion, and strict baseline continuity.
- Every Lane section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Lane closeout records weekly KPI deltas, governance decisions, and Lane integration expansion priorities.

## Weekly review quality checklist

- [ ] Includes KPI baseline deltas, confidence band, and anomaly narrative
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures pass-rate trend, reliability incidents, contributor signal quality, and recovery owner
- [ ] Artifact pack includes weekly brief, KPI dashboard, decision register, risk ledger, and execution log

## Weekly Review Closeout delivery board (legacy)

- [ ] Lane weekly brief committed
- [ ] Lane KPI dashboard snapshot exported
- [ ] Lane governance decision register published
- [ ] Lane risk and recovery ledger exported
- [ ] Lane integration expansion priorities drafted from Lane review

## Scoring model

Lane weighted score (0-100):

- Contract + command lane completeness: 25 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 30 points.
- Weekly review quality + governance handoff: 25 points.
