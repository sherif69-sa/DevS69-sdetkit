# Quickstart: Platform engineer

Use this lane when your job is platform reliability, aggregation, and cross-repo signal quality.

## Outcome

Keep portfolio reporting healthy and reduce triage time when failures appear.

## Commands

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
python scripts/check_canonical_path_drift.py --format json
```

## Required evidence

- Canonical artifacts in `build/`
- Drift-check output from `check_canonical_path_drift.py`
- Portfolio contract reference: `docs/portfolio-aggregation-schema.md`

## Escalation trigger

Escalate when schema compatibility or drift checks block reliable portfolio rollups.

## KPI focus

- `mean_time_to_triage_first_failure`
- `failed_release_gate_frequency`
