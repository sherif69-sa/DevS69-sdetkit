# Real repo adoption fixture

This fixture is a tiny Python repository-shaped project used to prove the
canonical SDETKit path from local run to CI artifact review.

## Fixture scope

- minimal `src/` + `tests/` layout
- deterministic tiny test
- no customer claims, benchmark claims, or synthetic dashboards

## Canonical commands

Run from this directory:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
```
