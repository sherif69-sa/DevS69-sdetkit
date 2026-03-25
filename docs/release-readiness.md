# Release readiness board

Release readiness composes weekly-review trend health and reliability-evidence posture into one release-candidate gate.

## Who should run release-readiness

- Maintainers deciding if a release tag can be cut this week.
- Team leads running release-readiness reviews and action tracking.
- Contributors preparing evidence for release notes.

## Score model

- Reliability-evidence score weight: 70%
- Weekly-review score weight: 30%

## Fast verification commands

```bash
python -m sdetkit release-readiness --format json --strict
python -m sdetkit release-readiness --emit-pack-dir docs/artifacts/release-readiness-pack --format json --strict
python -m sdetkit release-readiness --execute --evidence-dir docs/artifacts/release-readiness-pack/evidence --format json --strict
python scripts/check_release_readiness_contract.py
```

## Execution evidence mode

`--execute` runs the release-readiness command chain and writes deterministic logs into `--evidence-dir`.

## Closeout checklist

- [ ] Reliability-evidence gate status is `pass`.
- [ ] Weekly-review score meets threshold.
- [ ] Release-readiness score is reviewed by maintainers.
- [ ] Release-readiness recommendations are tracked in backlog.
