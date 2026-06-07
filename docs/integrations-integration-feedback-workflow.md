# Integration feedback workflow

Lane closes with a major upgrade that folds Lane growth campaign outcomes into docs/template upgrades and community touchpoint execution.

## Why Integration Feedback Completion matters

- Turns Lane growth campaign outcomes into deterministic integration feedback loops across docs, templates, and community operations.
- Protects quality with strict contract coverage, runnable commands, KPI thresholds, and rollback safety.
- Creates a deterministic handoff from Lane completion report into Lane trust FAQ expansion priorities.

## Required inputs (Lane)

- `docs/artifacts/growth-campaign-completion-pack/growth-campaign-completion-summary.json`
- `docs/artifacts/growth-campaign-completion-pack/growth-campaign-delivery-board.md`
- `docs/roadmap/plans/integration-feedback-plan.json`

## Command lane

```bash
python -m sdetkit integration-feedback-completion --format json --strict
python -m sdetkit integration-feedback-completion --emit-pack-dir docs/artifacts/integration-feedback-completion-pack --format json --strict
python -m sdetkit integration-feedback-completion --execute --evidence-dir docs/artifacts/integration-feedback-completion-pack/evidence --format json --strict
python scripts/check_integration_feedback_completion_contract.py
```

## Integration feedback contract

- Single owner + backup reviewer are assigned for Lane integration feedback execution and signoff.
- This lane references Lane outcomes, controls, and campaign continuity signals.
- Every Lane section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Lane completion report records docs-template upgrades, community touchpoint outcomes, and Lane trust FAQ priorities.

## Integration feedback quality checklist

- [ ] Includes baseline feedback volume, segmentation assumptions, and response SLA targets
- [ ] Every upgrade lane row has owner, execution window, KPI threshold, and risk flag
- [ ] CTA links point to docs/templates + runnable command evidence
- [ ] Scorecard captures docs adoption delta, community engagement delta, confidence, and rollback owner
- [ ] Artifact pack includes integration brief, feedback plan, template diffs, office-hours ledger, KPI scorecard, and execution log

## Delivery board

- [ ] Lane integration brief committed
- [ ] Lane integration feedback plan committed
- [ ] Lane template upgrade ledger exported
- [ ] Lane office-hours outcome ledger exported
- [ ] Lane trust FAQ priorities drafted from Lane feedback

## Scoring model

Integration Feedback Completion weighted score (0-100):

- Contract + command lane integrity (35)
- Lane continuity baseline quality (35)
- Feedback evidence data + delivery board completeness (30)
