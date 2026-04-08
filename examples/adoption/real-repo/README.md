# Real repo adoption fixture

This fixture is a tiny Python repository-shaped project used to prove the
canonical SDETKit path from local run to CI artifact review.

## Fixture scope

- minimal `src/` + `tests/` layout
- deterministic tiny test
- intentional first-run gate failures for realistic triage proof
- no customer claims, benchmark claims, or synthetic dashboards

## Canonical commands

Run from this directory:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json ; echo $? > build/gate-fast.rc
python -m sdetkit gate release --format json --out build/release-preflight.json ; echo $? > build/release-preflight.rc
python -m sdetkit doctor --format json --out build/doctor.json ; echo $? > build/doctor.rc
python ../../../scripts/real_repo_adoption_projection.py --fixture-root . --repo-root ../../.. --build-dir build --out build/adoption-proof-summary.json
```

## Expected truth model

- `gate-fast.rc = 2`, `gate-fast.json.ok = false`
- `release-preflight.rc = 2`, `release-preflight.json.ok = false`
- `doctor.rc = 0`, `doctor.json.ok = true`

If these expectations drift, investigate fixture/gate contract changes before
claiming trust lane health.
