# Portfolio reporting recipe (multi-repo)

Use this recipe to aggregate release-confidence evidence across repositories into one portfolio-level view.

## Objective

Create a weekly board that answers:

1. Which repos are release-ready?
2. Where is risk trending up?
3. Which teams need intervention this week?

## Inputs

Per repository, collect:

- `build/gate-fast.json`
- `build/release-preflight.json`
- `build/doctor.json`
- repository metadata (team, service tier, lane)

## Normalized record schema

```json
{
  "repo": "service-a",
  "team": "checkout",
  "lane": "scale",
  "timestamp": "2026-04-14T00:00:00Z",
  "gate_fast_ok": true,
  "gate_release_ok": true,
  "doctor_ok": true,
  "failed_steps_count": 0,
  "risk_level": "low"
}
```

## Aggregation steps

1. **Collect artifacts** from each target repository for the same reporting window.
2. **Normalize keys** into the schema above (especially `ok` and `failed_steps`).
3. **Compute risk level** using consistent thresholds:
   - `low`: all three checks pass
   - `medium`: exactly one gate fails
   - `high`: release gate fails or repeated failures
4. **Publish portfolio table** grouped by team/lane.
5. **Attach delta summary** from previous week.

## Weekly portfolio scorecard template

| Repo | Team | Lane | Gate fast | Gate release | Doctor | Failed steps | Risk |
|---|---|---|---|---|---|---:|---|
| service-a | checkout | scale | ✅ | ✅ | ✅ | 0 | low |
| service-b | growth | startup | ✅ | ❌ | ✅ | 2 | high |

## Portfolio roll-up metrics

- Total repos reporting
- `% repos low risk`
- `% repos with release gate failure`
- Median failed-steps count
- Week-over-week risk movement (up/down/no-change)

## Operating notes

- Keep one schema version per quarter to limit churn.
- Use a strict reporting cutoff (e.g., Friday 17:00 UTC).
- Flag missing data as `unknown` instead of implicitly passing.

## Tooling support

Use the adapter script `scripts/build_portfolio_scorecard.py` to generate a consolidated scorecard JSON from normalized records.
