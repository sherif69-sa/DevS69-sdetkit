# Workflow readiness baseline

Lane starts Release readiness with a measurable baseline carried over from Lane and a fixed weekly growth target set.

## Why Lane matters

- Converts Lane handoff into a measurable execution contract.
- Locks objective targets so weekly reviews can score progress without ambiguity.
- Forces evidence-backed growth planning before feature/distribution expansion.

## Required inputs (Lane)

- `docs/artifacts/baseline-wrap-pack/baseline-wrap-summary.json` (primary)
- `docs/artifacts/baseline-wrap-pack/baseline-wrap-release-readiness-backlog.md` (primary)

## Lane command lane

```bash
python -m sdetkit release-readiness-kickoff --format json --strict
python -m sdetkit release-readiness-kickoff --emit-pack-dir docs/artifacts/release-readiness-kickoff-pack --format json --strict
python -m sdetkit release-readiness-kickoff --execute --evidence-dir docs/artifacts/release-readiness-kickoff-pack/evidence --format json --strict
python scripts/check_phase2_kickoff_contract.py
```

## Baseline + weekly targets

- Baseline source: Lane activation score and completion report rollup.
- Week-1 Release readiness target: maintain activation score >= 95 and preserve strict pass.
- Week-1 growth target: publish 3 external-facing assets and 1 KPI checkpoint.
- Week-1 quality gate: every shipped action includes command evidence and a summary artifact.
- Week-1 decision gate: if any target misses, publish corrective actions in the next weekly review.

## Lane delivery board

- [ ] Lane baseline metrics snapshot emitted
- [ ] Lane release cadence checklist drafted
- [ ] Lane example asset plan (doctor) assigned
- [ ] Lane example asset plan (repo audit) assigned
- [ ] Lane weekly review preparation checklist ready

## Scoring model

Lane weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and quality baseline: 35 points.
- Week-1 target and delivery board lock: 15 points.
