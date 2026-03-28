# Growth Campaign Closeout — Growth campaign closeout lane

Cycle 81 closes with a major upgrade that converts Cycle 80 partner outreach outcomes into a growth-campaign execution pack.

## Why Growth Campaign Closeout matters

- Turns Cycle 80 partner outreach outcomes into growth campaign execution proof across docs, rollout, and demand loops.
- Protects launch quality with strict contract coverage, runnable commands, rollout guardrails, and rollback safety.
- Creates a deterministic handoff from Cycle 81 growth campaign closeout into Cycle 82 execution priorities.

## Required inputs (Cycle 80)

- `docs/artifacts/partner-outreach-closeout-pack/partner-outreach-closeout-summary.json`
- `docs/artifacts/partner-outreach-closeout-pack/partner-outreach-delivery-board.md`
- `docs/roadmap/plans/growth-campaign-plan.json`

## Command lane

```bash
python -m sdetkit growth-campaign-closeout --format json --strict
python -m sdetkit growth-campaign-closeout --emit-pack-dir docs/artifacts/growth-campaign-closeout-pack --format json --strict
python -m sdetkit growth-campaign-closeout --execute --evidence-dir docs/artifacts/growth-campaign-closeout-pack/evidence --format json --strict
python scripts/check_growth_campaign_closeout_contract.py
```

## Growth campaign contract

- Single owner + backup reviewer are assigned for Cycle 81 growth campaign execution and signoff.
- The Cycle 81 lane references Cycle 80 outcomes, controls, and KPI continuity signals.
- Every Cycle 81 section includes campaign CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Cycle 81 closeout records campaign outcomes, confidence notes, and Cycle 82 execution priorities.

## Growth campaign quality checklist

- [ ] Includes campaign baseline, audience assumptions, and launch cadence
- [ ] Every campaign lane row has owner, execution window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures campaign score delta, partner carryover delta, confidence, and rollback owner
- [ ] Artifact pack includes integration brief, campaign plan, execution ledger, KPI scorecard, and execution log

## Delivery board

- [ ] Cycle 81 integration brief committed
- [ ] Cycle 81 growth campaign plan committed
- [ ] Cycle 81 campaign execution ledger exported
- [ ] Cycle 81 campaign KPI scorecard snapshot exported
- [ ] Cycle 82 execution priorities drafted from Cycle 81 learnings

## Scoring model

Growth Campaign Closeout weighted score (0-100):

- Contract + command lane integrity (35)
- Cycle 80 continuity baseline quality (35)
- Campaign evidence data + delivery board completeness (30)
