# World-Class KPI Dashboard Baseline

This baseline is the first implementation pass for the "Stand up a KPI dashboard" item in the World-Class Quality Program.

Machine-readable baseline: `docs/artifacts/world-class-kpi-dashboard-baseline.json`.

## Ownership

| KPI lane | Primary owner | Backup owner | Review cadence |
| --- | --- | --- | --- |
| Reliability | QA Platform Lead | Release Manager | Weekly quality review |
| Velocity | Dev Experience Lead | Engineering Manager | Weekly quality review |
| Trust/Security | Security Champion | QA Platform Lead | Monthly trust review |
| Release readiness | Release Manager | QA Platform Lead | Per release candidate |

## KPI definitions

| KPI | Definition | Target | Source command / artifact |
| --- | --- | --- | --- |
| Mainline unit+integration pass rate | Passed test jobs / total test jobs on default branch over rolling 30 cycles | `>= 99%` | CI run history and test summaries |
| Change failure rate | Releases requiring rollback or hotfix / total releases in rolling 30 cycles | `< 5%` | Release board + changelog incidents |
| MTTR for release regression | Time from regression detection to verified recovery | `< 60 minutes` | Incident timeline artifacts |
| First successful local run | Time from clone to first successful `make test` for new contributor cohort | `< 30 minutes` | Onboarding diary samples |
| PR cycle time | Median time from PR open to merge | `< 24 hours` | SCM analytics export |
| Doc freshness SLA | Critical docs updated within 48h of behavior changes | `100%` compliance | Docs PR labels + merged timestamps |
| Critical vulns on default branch | Open critical vulnerabilities affecting supported branch | `0` | Security scan reports |
| Security drift remediation | Time from baseline drift detection to fix merge | `< 72 hours` | Security baseline incidents |
| Release evidence pack coverage | Releases that include evidence pack artifacts | `100%` | Release candidate artifact inventory |
| Rollback rate | Rolled back releases / total releases | `< 2%` | Release notes + incident logs |
| Merge-ready to release tag | Time from release-ready approval to tag creation | `< 2 hours` | Release timeline |

## Data collection contract (v1)

1. Collect weekly snapshots every Monday before quality review.
2. Publish a markdown summary in `docs/artifacts/` for auditability.
3. Store and update baseline metadata in `docs/artifacts/world-class-kpi-dashboard-baseline.json`.
4. Keep raw exports (JSON/CSV) attached to CI artifacts for 90 cycles.
5. Escalate any KPI that breaches target for 2 consecutive snapshots.

## Dashboard rollout checklist

- [x] Add first weekly snapshot artifact (`docs/artifacts/world-class-kpi-dashboard-weekly-2026-03-13.md`).
- [ ] Automate CI pass-rate extraction from workflow history.
- [ ] Automate PR cycle time extraction from SCM analytics export.
- [ ] Wire release evidence-pack coverage into release preflight checks.
- [ ] Backfill last 4 weeks of KPI values.

## Snapshot generation command

Generate the next weekly template from the machine-readable baseline:

```bash
python scripts/generate_world_class_kpi_snapshot.py --snapshot-date YYYY-MM-DD
```

To pre-fill KPI values and auto-calculate trend deltas from current + previous exported data:

```bash
python scripts/generate_world_class_kpi_snapshot.py \
  --snapshot-date YYYY-MM-DD \
  --metrics-json docs/artifacts/world-class-kpi-dashboard-metrics-sample.json \
  --previous-metrics-json docs/artifacts/world-class-kpi-dashboard-previous-metrics-sample.json \
  --strict-metrics \
  --summary-json docs/artifacts/world-class-kpi-dashboard-weekly-YYYY-MM-DD-summary.json  # includes target_eval + target_eval_counts + breach_kpi_ids \
  --fail-on-target-breach
```

## Immediate next actions

- Automate extraction for CI pass rate and PR cycle time.
- Add an evidence-pack coverage check to the release workflow.
- Backfill last 4 weeks of KPI values to establish trend lines.
