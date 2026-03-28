# Cycle 31 — Phase-2 kickoff baseline

Cycle 31 starts Phase-2 with a measurable baseline carried over from Cycle 30 and a fixed weekly growth target set.

## Why Cycle 31 matters

- Converts Cycle 30 handoff into a measurable execution contract.
- Locks objective targets so weekly reviews can score progress without ambiguity.
- Forces evidence-backed growth planning before feature/distribution expansion.

## Required inputs (Cycle 30)

- `docs/artifacts/phase1-wrap-pack/phase1-wrap-summary.json` (primary)
- `docs/artifacts/phase1-wrap-pack/phase1-wrap-phase2-backlog.md` (primary)

## Cycle 31 command lane

```bash
python -m sdetkit phase2-kickoff --format json --strict
python -m sdetkit phase2-kickoff --emit-pack-dir docs/artifacts/phase2-kickoff-pack --format json --strict
python -m sdetkit phase2-kickoff --execute --evidence-dir docs/artifacts/phase2-kickoff-pack/evidence --format json --strict
python scripts/check_phase2_kickoff_contract.py
```

## Baseline + weekly targets

- Baseline source: Cycle 30 activation score and closeout rollup.
- Week-1 Phase-2 target: maintain activation score >= 95 and preserve strict pass.
- Week-1 growth target: publish 3 external-facing assets and 1 KPI checkpoint.
- Week-1 quality gate: every shipped action includes command evidence and a summary artifact.
- Week-1 decision gate: if any target misses, publish corrective actions in the next weekly review.

## Cycle 31 delivery board

- [ ] Cycle 31 baseline metrics snapshot emitted
- [ ] Cycle 32 release cadence checklist drafted
- [ ] Cycle 33 demo asset plan (doctor) assigned
- [ ] Cycle 34 demo asset plan (repo audit) assigned
- [ ] Cycle 35 weekly review preparation checklist ready

## Scoring model

Cycle 31 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Cycle 30 continuity and quality baseline: 35 points.
- Week-1 target and delivery board lock: 15 points.
