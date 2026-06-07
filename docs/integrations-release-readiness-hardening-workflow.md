# Workflow hardening workflow

Lane closes with a major release readiness hardening upgrade that turns Lane KPI deep-audit outcomes into deterministic execution hardening governance.

## Why Lane matters

- Converts Lane KPI deep-audit evidence into repeatable hardening execution loops.
- Protects quality with ownership, command proof, and KPI rollback guardrails.
- Produces a deterministic handoff from Lane completion report into Lane pre-plan execution planning.

## Required inputs (Lane)

- `docs/artifacts/kpi-deep-audit-completion-pack/kpi-deep-audit-completion-summary.json`
- `docs/artifacts/kpi-deep-audit-completion-pack/kpi-deep-audit-delivery-board.md`

## Release Readiness Hardening command lane

```bash
python -m sdetkit release-readiness-hardening-completion-report --format json --strict
python -m sdetkit release-readiness-hardening-completion-report --emit-pack-dir docs/artifacts/release-readiness-hardening-completion-report-pack --format json --strict
python -m sdetkit release-readiness-hardening-completion-report --execute --evidence-dir docs/artifacts/release-readiness-hardening-completion-report-pack/evidence --format json --strict
python scripts/check_phase2_hardening_completion_contract.py
```

## release readiness hardening contract

- Single owner + backup reviewer are assigned for Lane release readiness hardening execution and signal triage.
- The Lane references Lane KPI deep-audit outcomes and unresolved risks.
- Every Lane section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Lane completion report records hardening outcomes and Lane pre-plan priorities.

## release readiness hardening quality checklist

- [ ] Includes friction-map digest, page hardening actions, and rollback strategy
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, confidence, and recovery owner for each KPI
- [ ] Artifact pack includes hardening brief, risk ledger, KPI scorecard, and execution log

## Lane delivery board

- [ ] Lane release readiness hardening brief committed
- [ ] Lane hardening plan reviewed with owner + backup
- [ ] Lane risk ledger exported
- [ ] Lane KPI scorecard snapshot exported
- [ ] Lane pre-plan priorities drafted from Lane learnings

## Scoring model

Lane weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 35 points.
- release readiness hardening contract lock + delivery board readiness: 15 points.
