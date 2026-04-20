# Toolkit Reliability SLOs (P1.3)

Status: Active proposal (v1)
Date: 2026-04-16

## Objective

Define reliability objectives for SDETKit itself so platform teams can operate the toolkit with measurable confidence.

## SLO set

### SLO-1: False positive rate (quality signal integrity)

- **SLI formula:**
  - `false_positive_rate = false_positive_failures / total_failures`
- **Target:** <= 5% weekly
- **Breach condition:** > 5% for 2 consecutive weeks

### SLO-2: Flaky check rate (stability)

- **SLI formula:**
  - `flaky_rate = flaky_runs / total_runs`
  - Flaky run = fails then passes on immediate rerun with no code change.
- **Target:** <= 2% weekly
- **Breach condition:** > 2% for 2 consecutive weeks

### SLO-3: PR lane latency (developer experience)

- **SLI formula:**
  - `pr_p95_minutes = p95(duration_minutes where lane=pr)`
- **Target:** <= 20 minutes p95
- **Breach condition:** > 20 minutes for 2 consecutive weeks

### SLO-4: Release lane latency (release readiness)

- **SLI formula:**
  - `release_p95_minutes = p95(duration_minutes where lane=release)`
- **Target:** <= 40 minutes p95
- **Breach condition:** > 40 minutes for 2 consecutive weeks

### SLO-5: Contract regression rate (compatibility)

- **SLI formula:**
  - `contract_regression_rate = contract_regression_runs / total_runs`
- **Target:** 0% on default branch
- **Breach condition:** any regression on default branch

## Error budget policy

- Weekly error budget applies to SLO-1 through SLO-4.
- Exceeding budget pauses non-essential feature rollout until remediation plan is approved.
- SLO-5 has zero-budget tolerance on default branch.

## Weekly reliability review playbook

1. Generate weekly reliability snapshot.
2. Compare SLI values against SLO thresholds.
3. Assign top 3 regressions to owning teams with due dates.
4. Decide mode:
   - **Green:** all SLOs within target.
   - **Yellow:** one SLO breached for one week.
   - **Red:** repeated breach or contract regression on default branch.
5. Publish summary + actions to platform review board.

## Recommended artifact outputs

- `docs/artifacts/toolkit-reliability-snapshot-YYYY-MM-DD.json`
- `docs/artifacts/toolkit-reliability-summary-YYYY-MM-DD.md`

## Machine-readable contract

See `docs/contracts/toolkit-reliability-slo.v1.json`.

## Acceptance criteria (P1.3)

- [x] SLOs defined for false positives, flakiness, and latency.
- [x] SLI formulas and breach conditions documented.
- [x] Weekly reliability review playbook documented.
- [x] Machine-readable SLO contract published.
