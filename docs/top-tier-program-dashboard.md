# Top-tier program dashboard (Q2 2026)

This dashboard is the weekly control plane for the **DevS69 SDETKit top-tier full-package transformation**.

- Program plan source: `plans/top-tier-repo-execution-plan-2026-q2.json`
- Leadership blueprint: [CTO full-package review](cto-full-package-review.md)
- Reporting cadence: Monday planning, Wednesday risk review, Friday closeout

## Weekly status snapshot

| Field | Value |
|---|---|
| Week ending | 2026-04-17 |
| Program status | Active |
| Delivery confidence | Green |
| Top blocker count | 0 |
| KPI movement | Seed baseline published |

## Workstream tracker

| Workstream | Owner role | Current phase | Status | This-week deliverable | Evidence |
|---|---|---|---|---|---|
| WS1 Product packaging | Product + DX | Phase 1 | In progress | Publish packaging lanes | [Packaging lanes](packaging-lanes.md) |
| WS2 Portfolio reporting | Platform engineering | Phase 1 | In progress | Publish portfolio reporting recipe | [Portfolio reporting recipe](portfolio-reporting-recipe.md) |
| WS3 Governance and lifecycle | Architecture + QA governance | Phase 1 | In progress | Publish compatibility matrix | [Policy compatibility matrix](policy-compatibility-matrix.md) |
| WS4 Commercialization enablement | PMM + Solutions | Phase 1 | In progress | Build role-based quickstart skeleton | [Role-based quickstarts](role-based-quickstarts.md) |
| WS5 Reliability and release excellence | Release engineering | Phase 1 | In progress | Publish support/escalation model | [Support and escalation model](support-and-escalation-model.md) |

## KPI board (contract baseline)

Track weekly:

1. `first_time_success_onboarding_rate`
2. `median_release_decision_time`
3. `failed_release_gate_frequency`
4. `rollback_rate`
5. `mean_time_to_triage_first_failure`
6. `docs_to_adoption_conversion`

### Baseline table

| KPI | Current | Target trend | Data source | Owner |
|---|---:|---|---|---|
| first_time_success_onboarding_rate | 0% (0/1 fixture seed) | Up | onboarding evidence logs | Product + DX |
| median_release_decision_time | N/A (timing instrumentation pending) | Down | gate-fast + release-preflight timestamps | Release engineering |
| failed_release_gate_frequency | 100% (1/1 fixture seed) | Down | gate artifact summaries | QA governance |
| rollback_rate | 0 (no incidents logged) | Down | release incident records | Release engineering |
| mean_time_to_triage_first_failure | N/A (incident timing fields pending) | Down | incident triage logs | Platform engineering |
| docs_to_adoption_conversion | N/A (telemetry pending) | Up | docs analytics + canonical path completions | PMM + Solutions |

## Blockers and decisions

| ID | Blocker / decision | Impact | Owner | ETA | Status |
|---|---|---|---|---|---|
| B-001 | No portfolio aggregate schema versioning convention | Delayed WS2 reporting | Platform engineering | 2026-04-24 | Closed 2026-04-15 |

## Weekly closeout template

### Completed
- [Portfolio aggregation schema](portfolio-aggregation-schema.md)
- [Portfolio scorecard sample (2026-04-17)](artifacts/portfolio-scorecard-sample-2026-04-17.json)
- [Role-based quickstarts](role-based-quickstarts.md)
- [KPI schema (v1)](kpi-schema.md)
- [KPI baseline snapshot (2026-04-17)](kpi-baseline-week-2026-04-17.md)
- [Generated KPI weekly sample (from portfolio)](artifacts/kpi-weekly-from-portfolio-2026-04-17.json)
- [KPI weekly contract check (2026-04-17)](artifacts/kpi-weekly-contract-check-2026-04-17.json)
- [Top-tier reporting contract check (2026-04-17)](artifacts/top-tier-contract-check-2026-04-17.json)
- [Top-tier bundle manifest (2026-04-17)](artifacts/top-tier-bundle-manifest-2026-04-17.json)
- [Top-tier bundle manifest check (2026-04-17)](artifacts/top-tier-bundle-manifest-check-2026-04-17.json)
- [Executive weekly report (2026-04-17)](executive-weekly-2026-04-17.md)
- [Executive monthly report (2026-04)](executive-monthly-2026-04.md)
- [Full release package checklist](full-release-package-checklist.md)

### KPI movement
- _Up / down / no-change summary with one-line interpretation per KPI._

### New blockers
- _List blocker, owner, and ETA._

### Next-week commitments
- _Maximum 5 deliverables with owners._
