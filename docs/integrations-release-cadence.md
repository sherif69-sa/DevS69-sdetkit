# Cycle 32 — Release cadence setup

Cycle 32 converts Cycle 31 baseline goals into a repeatable release operating cadence with a strict changelog quality gate.

## Why Cycle 32 matters

- Locks a weekly release rhythm that keeps growth loops predictable.
- Standardizes changelog quality so every release is user-legible and evidence-backed.
- Prevents rushed release drops by enforcing rollback and corrective-action rules.

## Required inputs (Cycle 31)

- `docs/artifacts/phase2-kickoff-pack/phase2-kickoff-summary.json` (primary)
- `docs/artifacts/phase2-kickoff-pack/phase2-kickoff-delivery-board.md` (primary)

## Cycle 32 command lane

```bash
python -m sdetkit release-cadence --format json --strict
python -m sdetkit release-cadence --emit-pack-dir docs/artifacts/release-cadence-pack --format json --strict
python -m sdetkit release-cadence --execute --evidence-dir docs/artifacts/release-cadence-pack/evidence --format json --strict
python scripts/check_release_cadence_contract.py
```

## Weekly cadence contract

- Cadence owner: release captain rotates weekly and is published in advance.
- Cadence rhythm: every Friday publish changelog, release narrative, and proof links.
- Cadence SLA: release artifact pack emitted within 60 minutes of merge cutoff.
- Rollback gate: if quality score < 95, postpone release and publish corrective actions.

## Changelog quality checklist

- [ ] Summary includes user-facing outcomes, not only internal refactors
- [ ] Every major change links to docs or runnable command evidence
- [ ] Breaking/risky changes include mitigation and rollback notes
- [ ] KPI movement for the week is captured in release notes
- [ ] Follow-up backlog items are explicitly listed with owners

## Cycle 32 delivery board

- [ ] Cycle 32 cadence calendar committed
- [ ] Cycle 32 changelog template committed
- [ ] Cycle 33 demo asset #1 scope frozen
- [ ] Cycle 34 demo asset #2 scope frozen
- [ ] Cycle 35 weekly review KPI frame locked

## Scoring model

Cycle 32 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Cycle 31 continuity and strict baseline carryover: 35 points.
- Cadence/changelog contract lock + delivery board readiness: 15 points.
