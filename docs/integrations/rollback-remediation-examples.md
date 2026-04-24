# Rollback and remediation examples (Phase 4 trust pack)

## Example 1: First-proof threshold breach on `main`

**Signal**
- `build/first-proof/weekly-threshold-check.json` reports `breach: true`
- owner escalation payload routes to `release-ops`

**Immediate response**
1. Freeze further merges to `main` until triage owner acknowledges.
2. Run `make first-proof-verify` on latest passing baseline commit and failing head commit.
3. Compare `first-proof-summary.json` and `weekly-trend.json` to isolate failing steps.

**Rollback**
1. Revert the highest-risk change set linked to first failing step.
2. Re-run `make first-proof-verify`.
3. Confirm threshold returns to non-breach state before reopening merges.

## Example 2: Dependency radar threshold breach (critical > 0)

**Signal**
- `docs/artifacts/phase3-dependency-radar-*.json` shows `threshold_check.breach: true`

**Immediate response**
1. Open weekly drift issue from template.
2. Assign package owners from priority queue.
3. Stage targeted upgrades in a remediation branch.

**Rollback**
1. If upgrades regress CI, revert only the failing package bump.
2. Pin to last compatible version in constraints/requirements.
3. Keep remaining safe upgrades and rerun radar + first-proof lanes.
