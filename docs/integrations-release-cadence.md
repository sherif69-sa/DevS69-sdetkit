# Lane — Release cadence setup

Lane converts Lane baseline goals into a repeatable release operating cadence with a strict changelog quality gate.

## Why Lane matters

- Locks a weekly release rhythm that keeps growth loops predictable.
- Standardizes changelog quality so every release is user-legible and evidence-backed.
- Prevents rushed release drops by enforcing rollback and corrective-action rules.

## Required inputs (Lane)

- `docs/artifacts/phase2-kickoff-pack/phase2-kickoff-summary.json` (primary)
- `docs/artifacts/phase2-kickoff-pack/phase2-kickoff-delivery-board.md` (primary)

## Lane command lane

```bash
python -m sdetkit release-cadence --format json --strict
python -m sdetkit release-cadence --emit-pack-dir docs/artifacts/release-cadence-pack --format json --strict
python -m sdetkit release-cadence --execute --evidence-dir docs/artifacts/release-cadence-pack/evidence --format json --strict
python scripts/check_release_cadence_contract.py
```

## Weekly cadence contract

- Cadence owner: release captain rotates weekly and is published in advance.
- Cadence rhythm: every Fripublish changelog, release narrative, and proof links.
- Cadence SLA: release artifact pack emitted within 60 minutes of merge cutoff.
- Rollback gate: if quality score < 95, postpone release and publish corrective actions.

## Changelog quality checklist

- [ ] Summary includes user-facing outcomes, not only internal refactors
- [ ] Every major change links to docs or runnable command evidence
- [ ] Breaking/risky changes include mitigation and rollback notes
- [ ] KPI movement for the week is captured in release notes
- [ ] Follow-up backlog items are explicitly listed with owners

## Lane delivery board

- [ ] Lane cadence calendar committed
- [ ] Lane changelog template committed
- [ ] Lane demo asset #1 scope frozen
- [ ] Lane demo asset #2 scope frozen
- [ ] Lane weekly review KPI frame locked

## Scoring model

Lane weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 35 points.
- Cadence/changelog contract lock + delivery board readiness: 15 points.
