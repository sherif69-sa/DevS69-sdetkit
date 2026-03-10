# Day 32 — Release cadence setup

Day 32 converts Day 31 baseline goals into a repeatable release operating cadence with a strict changelog quality gate.

## Why Day 32 matters

- Locks a weekly release rhythm that keeps growth loops predictable.
- Standardizes changelog quality so every release is user-legible and evidence-backed.
- Prevents rushed release drops by enforcing rollback and corrective-action rules.

## Required inputs (Day 31)

- `docs/artifacts/day31-phase2-pack/day31-phase2-kickoff-summary.json`
- `docs/artifacts/day31-phase2-pack/day31-delivery-board.md`

## Day 32 command lane

```bash
python -m sdetkit release-cadence --format json --strict
python -m sdetkit release-cadence --emit-pack-dir docs/artifacts/day32-release-cadence-pack --format json --strict
python -m sdetkit release-cadence --execute --evidence-dir docs/artifacts/day32-release-cadence-pack/evidence --format json --strict
python scripts/check_day32_release_cadence_contract.py
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

## Day 32 delivery board

- [ ] Day 32 cadence calendar committed
- [ ] Day 32 changelog template committed
- [ ] Day 33 demo asset #1 scope frozen
- [ ] Day 34 demo asset #2 scope frozen
- [ ] Day 35 weekly review KPI frame locked

## Scoring model

Day 32 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 31 continuity and strict baseline carryover: 35 points.
- Cadence/changelog contract lock + delivery board readiness: 15 points.
