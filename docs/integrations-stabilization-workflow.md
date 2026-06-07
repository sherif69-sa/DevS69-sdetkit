# Stabilization workflow

Lane closes with a major stabilization upgrade that turns Lane contributor-activation outcomes into deterministic KPI recovery and follow-through.

## Why Lane matters

- Converts Lane contributor outcomes into repeatable stabilization loops.
- Protects quality with ownership, command proof, and KPI rollback guardrails.
- Produces a deterministic handoff from Lane completion report into Lane deep audit planning.

## Required inputs (Lane)

- `docs/artifacts/contributor-activation-completion-pack/contributor-activation-completion-summary.json`
- `docs/artifacts/contributor-activation-completion-pack/contributor-activation-delivery-board.md`

## Stabilization Completion command lane

```bash
python -m sdetkit stabilization-completion --format json --strict
python -m sdetkit stabilization-completion --emit-pack-dir docs/artifacts/stabilization-completion-pack --format json --strict
python -m sdetkit stabilization-completion --execute --evidence-dir docs/artifacts/stabilization-completion-pack/evidence --format json --strict
python scripts/check_stabilization_completion_contract.py
```

## Stabilization contract

- Single owner + backup reviewer are assigned for Lane stabilization execution and KPI recovery.
- This lane references Lane contributor activation outcomes and unresolved risks.
- Every Lane section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Lane completion report records stabilization outcomes and Lane deep-audit priorities.

## Stabilization quality checklist

- [ ] Includes bottleneck digest, remediation experiments, and rollback strategy
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, delta, and confidence for each KPI
- [ ] Artifact pack includes stabilization brief, risk ledger, KPI scorecard, and execution log

## Lane delivery board

- [ ] Lane stabilization brief committed
- [ ] Lane stabilization plan reviewed with owner + backup
- [ ] Lane risk ledger exported
- [ ] Lane KPI scorecard snapshot exported
- [ ] Lane deep-audit priorities drafted from Lane learnings

## Scoring model

Lane weighted score (0-100):

- Contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 35 points.
- Stabilization contract lock + delivery board readiness: 15 points.
