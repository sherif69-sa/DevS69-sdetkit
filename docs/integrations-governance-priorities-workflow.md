# Governance priorities workflow

Lane closes with a major upgrade that converts Lane governance handoff outcomes into a deterministic governance priorities operating lane.

## Why Governance Priorities Completion matters

- Converts Lane governance handoff outcomes into reusable governance priorities decisions across governance rituals, roadmap reviews, and maintainer escalation paths.
- Protects quality with strict contract coverage, runnable commands, KPI thresholds, and rollback safety.
- Creates a deterministic handoff from Lane completion report into Lane governance priorities.

## Required inputs (Lane)

- `docs/artifacts/governance-handoff-completion-pack/governance-handoff-completion-summary.json`
- `docs/artifacts/governance-handoff-completion-pack/governance-handoff-delivery-board.md`
- `docs/roadmap/plans/governance-priorities-plan.json`

## Command lane

```bash
python -m sdetkit governance-priorities-completion --format json --strict
python -m sdetkit governance-priorities-completion --emit-pack-dir docs/artifacts/governance-priorities-completion-pack --format json --strict
python -m sdetkit governance-priorities-completion --execute --evidence-dir docs/artifacts/governance-priorities-completion-pack/evidence --format json --strict
python scripts/check_governance_priorities_completion_contract.py
```

## Governance priorities contract

- Single owner + backup reviewer are assigned for Lane governance priorities execution and signoff.
- This lane references Lane outcomes, controls, and trust continuity signals.
- Every Lane section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Lane completion report records governance priorities pack upgrades, storyline outcomes, and Lane governance priorities.

## Governance priorities quality checklist

- [ ] Includes baseline evidence coverage, objection segmentation assumptions, and response SLA targets
- [ ] Every narrative lane row has owner, execution window, KPI threshold, and risk flag
- [ ] CTA links point to narrative docs/templates + runnable command evidence
- [ ] Scorecard captures governance priorities adoption delta, objection deflection delta, confidence, and rollback owner
- [ ] Artifact pack includes narrative brief, evidence plan, template diffs, outcome ledger, KPI scorecard, and execution log

## Delivery board

- [ ] Lane evidence brief committed
- [ ] Lane governance priorities plan committed
- [ ] Lane narrative template upgrade ledger exported
- [ ] Lane storyline outcomes ledger exported
- [ ] Lane governance priorities drafted from Lane outcomes

## Scoring model

Lane weights continuity + execution contract + governance artifact readiness for a 100-point activation score.
