# Quickstart: Release owner

Use this lane when your job is making final go/no-go decisions for a version cut.

## Outcome

Ship with deterministic evidence attached to each release decision.

## Commands

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
```

## Required evidence

- `build/gate-fast.json`
- `build/release-preflight.json`
- `build/doctor.json`

## Decision rule

- **Ship** when gate artifacts show `ok: true` and no blocking failed steps.
- **No ship** when either gate artifact is not healthy; open incident/severity per escalation model.

## KPI focus

- `median_release_decision_time`
- `rollback_rate`
