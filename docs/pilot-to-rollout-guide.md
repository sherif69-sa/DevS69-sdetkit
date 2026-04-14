# Pilot to rollout guide

Use this guide to move from evaluation to production adoption with measurable exit criteria.

## Stage 1: Evaluation

### Goal
Prove canonical path works in representative repositories.

### Entry criteria
- Team sponsor and release owner assigned.
- Baseline repo selected.

### Exit criteria
- `gate fast`, `gate release`, and `doctor` run successfully in at least one target repo.
- Initial KPI baseline captured.

## Stage 2: Pilot

### Goal
Validate repeatability across multiple teams/repos.

### Entry criteria
- Evaluation exit criteria complete.
- Lane selected (Startup/Scale/Regulated).

### Exit criteria
- At least 3 repos onboarded (or agreed pilot size).
- Weekly dashboard in use for minimum 2 cycles.
- Incident/escalation flow exercised at least once (tabletop or real incident).

## Stage 3: Production rollout

### Goal
Operationalize portfolio reporting and governance at org level.

### Entry criteria
- Pilot criteria complete with leadership sign-off.

### Exit criteria
- Portfolio reporting recipe operating weekly.
- Compatibility and deprecation policy actively enforced.
- Executive weekly report adopted in leadership cadence.

## Recommended 30/60/90 checkpoints

- **Day 30:** evaluation complete + KPI baseline.
- **Day 60:** pilot steady-state + governance docs active.
- **Day 90:** portfolio reporting + executive rhythm institutionalized.

## Common failure modes and mitigations

| Failure mode | Signal | Mitigation |
|---|---|---|
| Scope too broad | Too many repos in initial pilot | Limit to highest-impact services first |
| No clear ownership | Repeated missed commitments | Assign DRI per workstream and publish weekly |
| Data inconsistency | KPI disputes every week | Freeze schema for reporting window |
