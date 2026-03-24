# Release readiness board (Day 19)

Day 19 composes Day 14 weekly trend health and Day 18 reliability posture into one release-candidate gate.

## Who should run Day 19

- Maintainers deciding if a release tag can be cut this week.
- Team leads running closeout meetings and action tracking.
- Contributors preparing evidence for release notes.

## Score model

- Day 18 reliability score weight: 70%
- Day 14 KPI score weight: 30%

## Fast verification commands

```bash
python -m sdetkit release-readiness --format json --strict
python -m sdetkit release-readiness --emit-pack-dir docs/artifacts/release-readiness-pack --format json --strict
python -m sdetkit release-readiness --execute --evidence-dir docs/artifacts/release-readiness-pack/evidence --format json --strict
python scripts/check_day19_release_readiness_board_contract.py
```

## Execution evidence mode

`--execute` runs the Day 19 command chain and writes deterministic logs into `--evidence-dir`.

## Closeout checklist

- [ ] Day 18 reliability gate status is `pass`.
- [ ] Day 14 KPI score meets threshold.
- [ ] Day 19 release score is reviewed by maintainers.
- [ ] Day 19 recommendations are tracked in backlog.
