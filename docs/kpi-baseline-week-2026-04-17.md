# KPI baseline snapshot — week ending 2026-04-17

This snapshot captures the first measurable KPI baseline for the top-tier program.

## Scope and caveat

- Baseline is computed from the current real-repo adoption fixture evidence in `artifacts/adoption/real-repo-golden`.
- This is a **seed baseline** for instrumentation validation, not a production fleet benchmark.

## KPI baseline values

| KPI | Baseline value | Method | Notes |
|---|---:|---|---|
| first_time_success_onboarding_rate | 0% (0/1) | Count `ok=true` in first release preflight runs | Fixture sample shows `ok=false` in `release-preflight.json` |
| median_release_decision_time | N/A | Requires start/end timing instrumentation | Add timestamp capture to gate run pipeline |
| failed_release_gate_frequency | 100% (1/1) | Count failed release-gate runs / total runs | Fixture sample has `failed_steps` in release preflight |
| rollback_rate | 0 (no incidents logged) | Weekly incident ledger count | No rollback incident record captured this week |
| mean_time_to_triage_first_failure | N/A | Requires incident-open and first-triage timestamps | Add incident timeline fields to records |
| docs_to_adoption_conversion | N/A | Requires docs analytics + completion tracking | Add docs CTA + completion event wiring |

## Evidence sources

- `artifacts/adoption/real-repo-golden/gate-fast.json`
- `artifacts/adoption/real-repo-golden/release-preflight.json`
- `docs/kpi-weekly-2026-04-17.json`
- `docs/top-tier-program-dashboard.md`

## Next instrumentation actions

1. Add timestamp fields to canonical gate wrappers for decision-time metrics.
2. Add incident timeline fields to enable MTTTF calculations.
3. Add docs conversion tracking hooks and weekly export.
