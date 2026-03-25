# Release readiness report

## Release readiness report

Release readiness provides a deterministic **release readiness board** that fuses reliability-evidence and weekly-review posture into one strict go/no-go signal.

## What shipped

- Added `sdetkit release-readiness` CLI to aggregate reliability-evidence and weekly-review summary inputs.
- Added strict docs contract checks, a default release-readiness integration page, and a weighted release score model.
- Added emitted pack outputs (summary, scorecard, checklist, validation commands, release decision note) for handoff.
- Added execution evidence mode with deterministic command logs and summary JSON.

## Validation commands

```bash
python -m sdetkit release-readiness --format text
python -m sdetkit release-readiness --format json --strict
python -m sdetkit release-readiness --emit-pack-dir docs/artifacts/release-readiness-pack --format json --strict
python -m sdetkit release-readiness --execute --evidence-dir docs/artifacts/release-readiness-pack/evidence --format json --strict
python scripts/check_release_readiness_contract.py
```

## Closeout

Release readiness now provides one release score, one strict gate lane, and one evidence bundle that can be attached directly to weekly review and release-candidate reviews.
