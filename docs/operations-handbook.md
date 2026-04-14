# Operations handbook (weekly health + incident + upgrades)

This handbook defines the recurring operator workflow for running SDETKit as a platform.

## 1) Weekly health review

**Cadence:** every Wednesday.

Checklist:

1. Review KPI board from the [Top-tier program dashboard](top-tier-program-dashboard.md).
2. Confirm each workstream has owner, status, and evidence links.
3. Identify top 3 risks and assign mitigation owners.
4. Publish a mid-week status note.

## 2) Incident triage flow

1. Detect signal (failed release gate, doctor regression, schema drift).
2. Assign severity via [Support and escalation model](support-and-escalation-model.md).
3. Start incident record and assign incident commander.
4. Mitigate and communicate using severity update cadence.
5. Close incident with root cause and follow-up tasks.

## 3) Upgrade planning lane

Run this monthly before release train updates:

1. Review [Policy compatibility matrix](policy-compatibility-matrix.md).
2. Inventory legacy usage via migration tooling/docs.
3. Run canonical path in staging repos.
4. Publish upgrade plan (timeline, owners, rollback plan).
5. Approve rollout wave sequence (startup -> scale -> regulated).

## 4) Release owner checklist

For every version cut:

- [ ] Validate gate fast and gate release artifacts are attached.
- [ ] Confirm doctor output is healthy.
- [ ] Confirm docs navigation reflects new/changed controls.
- [ ] Confirm compatibility/deprecation notes are updated.
- [ ] Confirm support/escalation notices are prepared if needed.

## 5) Evidence policy

Every operational claim should reference one of:

- canonical gate artifacts
- dashboard status entries
- incident records
- release notes with migration guidance
