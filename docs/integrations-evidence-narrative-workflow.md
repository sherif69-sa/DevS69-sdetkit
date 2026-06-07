# Evidence narrative workflow

Lane closes with a major upgrade that converts Lane trust FAQ outcomes into a deterministic evidence narrative operating lane.

## Why Evidence Narrative Completion matters

- Converts Lane trust FAQ outcomes into reusable evidence narratives across docs, release notes, and escalation playbooks.
- Protects quality with strict contract coverage, runnable commands, KPI thresholds, and rollback safety.
- Creates a deterministic handoff from Lane completion report into Lane release priorities.

## Required inputs (Lane)

- `docs/artifacts/trust-faq-expansion-completion-pack/trust-faq-expansion-completion-summary.json`
- `docs/artifacts/trust-faq-expansion-completion-pack/trust-faq-expansion-delivery-board.md`
- `docs/roadmap/plans/evidence-narrative-plan.json`

## Command lane

```bash
python -m sdetkit evidence-narrative-completion --format json --strict
python -m sdetkit evidence-narrative-completion --emit-pack-dir docs/artifacts/evidence-narrative-completion-pack --format json --strict
python -m sdetkit evidence-narrative-completion --execute --evidence-dir docs/artifacts/evidence-narrative-completion-pack/evidence --format json --strict
python scripts/check_evidence_narrative_completion_contract.py
```

## Evidence narrative contract

- Single owner + backup reviewer are assigned for Lane evidence narrative execution and signoff.
- This lane references Lane outcomes, controls, and trust continuity signals.
- Every Lane section includes docs/template CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Lane completion report records evidence narrative pack upgrades, storyline outcomes, and Lane release priorities.

## Evidence narrative quality checklist

- [ ] Includes baseline evidence coverage, objection segmentation assumptions, and response SLA targets
- [ ] Every narrative lane row has owner, execution window, KPI threshold, and risk flag
- [ ] CTA links point to narrative docs/templates + runnable command evidence
- [ ] Scorecard captures evidence narrative adoption delta, objection deflection delta, confidence, and rollback owner
- [ ] Artifact pack includes narrative brief, evidence plan, template diffs, outcome ledger, KPI scorecard, and execution log

## Delivery board

- [ ] Lane evidence brief committed
- [ ] Lane evidence narrative plan committed
- [ ] Lane narrative template upgrade ledger exported
- [ ] Lane storyline outcomes ledger exported
- [ ] Lane release priorities drafted from Lane outcomes

## Scoring model

Lane weights continuity + execution contract + artifact readiness for a 100-point activation score.
