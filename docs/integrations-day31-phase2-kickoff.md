# Day 31 — Phase-2 kickoff baseline

Day 31 starts Phase-2 with a measurable baseline carried over from Day 30 and a fixed weekly growth target set.

## Why Day 31 matters

- Converts Day 30 handoff into a measurable execution contract.
- Locks objective targets so weekly reviews can score progress without ambiguity.
- Forces evidence-backed growth planning before feature/distribution expansion.

## Required inputs (Day 30)

- `docs/artifacts/day30-wrap-pack/day30-phase1-wrap-summary.json`
- `docs/artifacts/day30-wrap-pack/day30-phase2-backlog.md`

## Day 31 command lane

```bash
python -m sdetkit day31-phase2-kickoff --format json --strict
python -m sdetkit day31-phase2-kickoff --emit-pack-dir docs/artifacts/day31-phase2-pack --format json --strict
python -m sdetkit day31-phase2-kickoff --execute --evidence-dir docs/artifacts/day31-phase2-pack/evidence --format json --strict
python scripts/check_day31_phase2_kickoff_contract.py
```

## Baseline + weekly targets

- Baseline source: Day 30 activation score and closeout rollup.
- Week-1 Phase-2 target: maintain activation score >= 95 and preserve strict pass.
- Week-1 growth target: publish 3 external-facing assets and 1 KPI checkpoint.
- Week-1 quality gate: every shipped action includes command evidence and a summary artifact.
- Week-1 decision gate: if any target misses, publish corrective actions in the next weekly review.

## Day 31 delivery board

- [ ] Day 31 baseline metrics snapshot emitted
- [ ] Day 32 release cadence checklist drafted
- [ ] Day 33 demo asset plan (doctor) assigned
- [ ] Day 34 demo asset plan (repo audit) assigned
- [ ] Day 35 weekly review preparation checklist ready

## Scoring model

Day 31 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 30 continuity and quality baseline: 35 points.
- Week-1 target and delivery board lock: 15 points.
