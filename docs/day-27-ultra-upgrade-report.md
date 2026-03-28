# Cycle 27 ultra upgrade report — KPI audit closeout

## What shipped

- Added `kpi-audit` command to compare baseline vs current KPI snapshots and enforce strict closeout gates.
- Added Cycle 27 docs contract validation for KPI audit guidance and command lane completeness.
- Added deterministic Cycle 27 artifact pack generation (scorecard, delta table, corrective action plan, snapshots).
- Added dedicated Cycle 27 contract-check script and automated tests.

## Key command paths

```bash
python -m sdetkit kpi-audit --format json --strict
python -m sdetkit kpi-audit --emit-pack-dir docs/artifacts/kpi-audit-pack --format json --strict
python -m sdetkit kpi-audit --execute --evidence-dir docs/artifacts/kpi-audit-pack/evidence --format json --strict
python scripts/check_kpi_audit_contract.py
```

## Closeout criteria

- Cycle 27 score >= 90 with no critical failures.
- Baseline/current KPI snapshots valid and published.
- README/docs index discoverability links in place.
- Evidence bundle generated and review-ready.
