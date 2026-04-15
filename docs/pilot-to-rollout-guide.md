# Pilot to rollout guide

Use this guide to move from evaluation to production adoption with measurable exit criteria.

## Stage 1: Evaluation

### Goal
Prove canonical path works in representative repositories.

### Entry criteria
- Team sponsor and release owner assigned.
- Baseline repo selected.
- Target lane selected (Startup/Scale/Regulated).

### Exit criteria (measurable)

| Check | Threshold | Evidence |
|---|---|---|
| Canonical path runs in baseline repo | 1/1 successful run with artifacts produced | `build/gate-fast.json`, `build/release-preflight.json`, `build/doctor.json` |
| Onboarding baseline captured | Week-1 seed KPI payload committed | `docs/kpi-weekly-<date>.json` |
| Ownership model set | All 5 workstreams have DRI listed | `docs/top-tier-program-dashboard.md` |

## Stage 2: Pilot

### Goal
Validate repeatability across multiple teams/repos.

### Entry criteria
- Evaluation exit criteria complete.
- Lane selected (Startup/Scale/Regulated).
- Weekly status cadence announced.

### Exit criteria (measurable)

| Check | Threshold | Evidence |
|---|---|---|
| Pilot coverage | At least 3 repos onboarded (or approved pilot size) | Portfolio scorecard JSON |
| Weekly operating rhythm | 2 consecutive weekly cycles completed | Weekly executive reports |
| Escalation readiness | 1 incident/escalation workflow exercised | Incident log + support model reference |
| Portfolio contract adoption | Scorecard payload emitted with `schema_version` and required totals | `docs/artifacts/portfolio-scorecard-*.json` |

## Stage 3: Production rollout

### Goal
Operationalize portfolio reporting and governance at org level.

### Entry criteria
- Pilot criteria complete with leadership sign-off.
- Monthly leadership review template ready.

### Exit criteria (measurable)

| Check | Threshold | Evidence |
|---|---|---|
| Portfolio reporting operational | Weekly scorecard generated for active repos for 4 straight weeks | Portfolio scorecard artifacts |
| Governance enforcement active | Compatibility/deprecation reviews completed monthly | Governance policy docs + review notes |
| Leadership reporting institutionalized | Weekly + monthly executive reports used in cadence | `docs/executive-weekly-*.md`, `docs/executive-monthly-*.md` |
| Release package readiness | Full release package checklist passes for release train | `docs/full-release-package-checklist.md` |

## Recommended 30/60/90 checkpoints

- **Day 30:** evaluation complete + KPI baseline payload + DRI assignment.
- **Day 60:** pilot steady-state + 2 weekly cycles + escalation rehearsal.
- **Day 90:** 4-week portfolio reporting streak + monthly leadership review + release package checklist adoption.

## Stage gate command set

Use this command set before each stage sign-off:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
python scripts/build_portfolio_scorecard.py --in <normalized-input> --out <portfolio-scorecard.json> --schema-version 1.0.0 --window-start <YYYY-MM-DD> --window-end <YYYY-MM-DD>
```

## Common failure modes and mitigations

| Failure mode | Signal | Mitigation |
|---|---|---|
| Scope too broad | Too many repos in initial pilot | Limit to highest-impact services first |
| No clear ownership | Repeated missed commitments | Assign DRI per workstream and publish weekly |
| Data inconsistency | KPI disputes every week | Freeze schema for reporting window |
| Escalation drift | Severity decisions differ by team | Enforce one support model + monthly calibration |

## WS4 execution acceptance checklist

Use this checklist when executing **Point 6 (WS4 commercialization + program closeout)** in the CTO workflow.

- [x] Pilot/evaluation/production exit criteria are measurable and documented.
- [x] Role-oriented onboarding references are published.
- [x] Weekly + monthly executive reporting templates are documented.
- [x] Rollout stage-gate command path is published.

Evidence links:

- [Role-based quickstarts](role-based-quickstarts.md)
- [Executive weekly template](executive-weekly-template.md)
- [Executive monthly template](executive-monthly-template.md)
- [Top-tier program dashboard](top-tier-program-dashboard.md)
