# World-Class KPI Dashboard Weekly Snapshot — 2026-03-13

Generated from `docs/artifacts/world-class-kpi-dashboard-baseline.json`.

## Snapshot metadata

- Program: `world-class-quality`
- Dashboard: `world-class-kpi`
- Baseline version: `v1`
- Snapshot window: `rolling-30-impact`
- Review cadence: `weekly`
- KPI coverage: `0/11` with provided metric values

## KPI scorecard

| KPI ID | Lane | KPI | Target | Current value | Delta vs previous | Status | Evidence link |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mainline_pass_rate | reliability | Mainline unit+integration pass rate | `>=99%` | TODO | TODO | TODO | TODO |
| change_failure_rate | reliability | Change failure rate | `<5%` | TODO | TODO | TODO | TODO |
| release_regression_mttr | reliability | MTTR for release regression | `<60m` | TODO | TODO | TODO | TODO |
| first_successful_local_run | velocity | First successful local run | `<30m` | TODO | TODO | TODO | TODO |
| pr_cycle_time | velocity | PR impact time median | `<24h` | TODO | TODO | TODO | TODO |
| doc_freshness_sla | velocity | Doc freshness SLA | `100%` | TODO | TODO | TODO | TODO |
| critical_vulns | trust_security | Critical vulns on default branch | `0` | TODO | TODO | TODO | TODO |
| security_drift_remediation | trust_security | Security drift remediation | `<72h` | TODO | TODO | TODO | TODO |
| evidence_pack_coverage | release_readiness | Release evidence pack coverage | `100%` | TODO | TODO | TODO | TODO |
| rollback_rate | release_readiness | Rollback rate | `<2%` | TODO | TODO | TODO | TODO |
| merge_ready_to_tag | release_readiness | Merge-ready to release tag | `<2h` | TODO | TODO | TODO | TODO |

## Owners on duty

| Lane | Primary owner | Backup owner |
| --- | --- | --- |
| Reliability | QA Platform Lead | Release Manager |
| Velocity | Dev Experience Lead | Engineering Manager |
| Trust Security | Security Champion | QA Platform Lead |
| Release Readiness | Release Manager | QA Platform Lead |

## Breach escalation

- [ ] No KPI breached target for 2 consecutive snapshots.
- [ ] If breached, incident owner and ETA are recorded.

## Notes

- Trend deltas are auto-calculated from `--previous-metrics-json` when provided.
- Inline `previous_value` in `--metrics-json` is also supported as a fallback.
- Use `--strict-metrics` to fail generation when any baseline KPI is missing.
- Use `--summary-json` to emit a machine-readable snapshot rollup with target evaluation and breach IDs.
- TODO: Attach raw export links for CI/SCM/security data.
