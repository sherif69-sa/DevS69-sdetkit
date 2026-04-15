# Quickstart: QA governance

Use this lane when your job is policy enforcement, compatibility checks, and governance readiness.

## Outcome

Ensure release confidence controls remain policy-compliant across teams.

## Commands

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
python scripts/check_canonical_path_drift.py --format json
python scripts/generate_artifact_contract_index.py
```

## Required evidence

- Canonical artifacts in `build/`
- Contract index output for review traceability
- Policy references:
  - `docs/policy-compatibility-matrix.md`
  - `docs/support-and-escalation-model.md`

## Governance gate

Open a policy action when compatibility expectations or escalation/SLO commitments are not met.

## KPI focus

- `failed_release_gate_frequency`
- `docs_to_adoption_conversion`
