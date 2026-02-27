# Day 81 — Growth campaign closeout lane

Day 81 closes with a major upgrade that converts Day 80 partner outreach outcomes into a growth-campaign execution pack.

## Why Day 81 matters

- Turns Day 80 partner outreach outcomes into growth campaign execution proof across docs, rollout, and demand loops.
- Protects launch quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.
- Creates a deterministic handoff from Day 81 growth campaign closeout into Day 82 execution priorities.

## Required inputs (Day 80)

- `docs/artifacts/day80-partner-outreach-closeout-pack/day80-partner-outreach-closeout-summary.json`
- `docs/artifacts/day80-partner-outreach-closeout-pack/day80-delivery-board.md`
- `.day81-growth-campaign-plan.json`

## Day 81 command lane

```bash
python -m sdetkit day81-growth-campaign-closeout --format json --strict
python -m sdetkit day81-growth-campaign-closeout --emit-pack-dir docs/artifacts/day81-growth-campaign-closeout-pack --format json --strict
python -m sdetkit day81-growth-campaign-closeout --execute --evidence-dir docs/artifacts/day81-growth-campaign-closeout-pack/evidence --format json --strict
python scripts/check_day81_growth_campaign_closeout_contract.py
```

## Growth campaign contract

- Single owner + backup reviewer are assigned for Day 81 growth campaign execution and signoff.
- The Day 81 lane references Day 80 outcomes, controls, and KPI continuity signals.
- Every Day 81 section includes campaign CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Day 81 closeout records campaign outcomes, confidence notes, and Day 82 execution priorities.

## Growth campaign quality checklist

- [ ] Includes campaign baseline, audience assumptions, and launch cadence
- [ ] Every campaign lane row has owner, execution window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures campaign score delta, partner carryover delta, confidence, and rollback owner
- [ ] Artifact pack includes integration brief, campaign plan, execution ledger, KPI scorecard, and execution log

## Day 81 delivery board

- [ ] Day 81 integration brief committed
- [ ] Day 81 growth campaign plan committed
- [ ] Day 81 campaign execution ledger exported
- [ ] Day 81 campaign KPI scorecard snapshot exported
- [ ] Day 82 execution priorities drafted from Day 81 learnings

## Scoring model

Day 81 weighted score (0-100):

- Contract + command lane integrity (35)
- Day 80 continuity baseline quality (35)
- Campaign evidence data + delivery board completeness (30)
