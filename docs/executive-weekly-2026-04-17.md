# Executive weekly report

## Week ending
- Date: 2026-04-17
- Program status: Green
- Executive summary (3 bullets max):
  - WS2 blocker B-001 closed with a published portfolio schema versioning convention.
  - WS4 moved to in-progress with role-based quickstart skeletons for three core roles.
  - KPI board moved from TBD to first seed baseline using fixture evidence.

## KPI movement

| KPI | This week | Last week | Direction | Note |
|---|---:|---:|---|---|
| first-time-success onboarding rate | 0% (0/1) | N/A | no-change | Seed baseline from real-repo fixture evidence |
| median release decision time | N/A | N/A | no-change | Timing instrumentation pending |
| failed release gate frequency | 100% (1/1) | N/A | no-change | Fixture run intentionally triage-oriented |
| rollback rate | 0 | N/A | no-change | No rollback incidents logged this week |
| mean time to triage first failure | N/A | N/A | no-change | Incident timestamp fields pending |
| docs-to-adoption conversion | N/A | N/A | no-change | Analytics + completion hooks pending |

## Portfolio risk snapshot

| Risk tier | Repo count | Change vs last week | Top owners |
|---|---:|---:|---|
| High | 1 | N/A | Platform engineering |
| Medium | 0 | N/A | Release engineering |
| Low | 0 | N/A | Product + DX |

## Decisions needed (leadership)

1. Approve KPI instrumentation slice for decision-time and triage-time timestamps by 2026-04-24 (Owner: Platform engineering).
2. Approve docs conversion telemetry approach for PMM reporting by 2026-04-24 (Owner: PMM + Solutions).

## Blockers requiring escalation

| Blocker | Impact | Owner | ETA | Escalation requested |
|---|---|---|---|---|
| None this week | — | — | — | No |

## Next-week commitments (max 5)

1. Add timing instrumentation fields to gate execution outputs (Owner: Release engineering, due 2026-04-22).
2. Add incident timeline schema for MTTTF tracking (Owner: Platform engineering, due 2026-04-23).
3. Add docs conversion event mapping draft (Owner: PMM + Solutions, due 2026-04-24).
