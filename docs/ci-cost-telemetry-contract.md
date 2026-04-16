# CI Cost Telemetry Contract (P1.2)

Status: Active proposal (v1)  
Date: 2026-04-16

## Objective

Standardize weekly CI cost telemetry so engineering leadership can track runtime spend, artifact growth, and workflow frequency by lane.

## Scope

This contract defines the minimum telemetry payload for each weekly reporting cycle:

1. **Minutes by lane** (PR, release, security, docs, maintenance)
2. **Artifact size by lane** (MB)
3. **Run frequency by lane** (count per week)
4. **Failure rate by lane** (%)

## Data contract

Machine-readable schema path:  
`docs/contracts/ci-cost-telemetry.v1.json`

### Required top-level fields

- `schema_version`
- `generated_at_utc`
- `window`
- `repo`
- `lanes`
- `totals`

### Lane record (required fields)

- `lane_id`
- `workflow_names`
- `run_count`
- `minutes_total`
- `minutes_p50`
- `minutes_p95`
- `artifact_mb_total`
- `failure_rate_percent`

## Weekly snapshot location

Recommended output path pattern:

- `docs/artifacts/ci-cost-telemetry-YYYY-MM-DD.json`

## KPI thresholds (initial)

- PR lane p95 runtime <= 20 minutes
- Release lane p95 runtime <= 40 minutes
- Weekly artifact growth <= +15% week-over-week
- Failed run rate <= 10% per lane (except known maintenance windows)

## Dashboard ingestion guide

### Step 1 — Produce snapshot

Generate weekly telemetry JSON and validate against schema.

### Step 2 — Publish artifact

Store validated snapshot in `docs/artifacts/` and attach to weekly review issue.

### Step 3 — Dashboard mapping

Map fields:

- `totals.minutes_total` -> overall CI minute spend
- `lanes[*].minutes_p95` -> runtime risk by lane
- `lanes[*].artifact_mb_total` -> artifact storage pressure
- `lanes[*].failure_rate_percent` -> reliability trend

### Step 4 — Operating review

In weekly platform review:

- Flag lanes above thresholds.
- Open remediation tasks for top 3 regressions.
- Track trend deltas over 4-week rolling window.

## Rollout phases

1. **Shadow mode (2 weeks):** collect without enforcement.
2. **Advisory mode (2 weeks):** warn on threshold exceedance.
3. **Policy mode:** block selected releases if release lane breaches policy for 2 consecutive weeks.

## Acceptance criteria (P1.2)

- [x] CI telemetry contract documented.
- [x] Machine-readable schema published.
- [x] Dashboard ingestion mapping documented.
- [x] Rollout phases defined.
