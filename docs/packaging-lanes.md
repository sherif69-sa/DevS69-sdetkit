# Packaging lanes: Startup, Scale, Regulated

This document defines the three product packaging lanes used by the top-tier program.

## 1) Startup lane

**Ideal for:** small teams optimizing for speed with essential safeguards.

### Minimum controls
- Canonical release confidence path enabled (`gate fast`, `gate release`, `doctor`)
- Machine-readable artifact retention for every run
- Named release owner for every release decision

### Command path (baseline)
```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
```

### Success KPI emphasis
- first-time-success onboarding rate
- median release decision time

## 2) Scale lane

**Ideal for:** multi-team organizations requiring repeatability and governance signals.

### Minimum controls
- Startup lane controls, plus:
- Team-level quality gate ownership matrix
- Weekly KPI review in program dashboard
- Compatibility/deprecation policy enforced for CLI + artifact schema

### Command path (baseline + governance checks)
```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
python scripts/check_canonical_path_drift.py --format json
```

### Success KPI emphasis
- failed release gate frequency
- mean time to triage first failure

## 3) Regulated lane

**Ideal for:** organizations needing auditability, documented change control, and escalation contracts.

### Minimum controls
- Scale lane controls, plus:
- Support severity model with response SLOs
- Documented deprecation windows and migration runbooks
- Release checklist evidence attached to every version cut

### Command path (baseline + governance + evidence hardening)
```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
python scripts/check_canonical_path_drift.py --format json
python scripts/generate_artifact_contract_index.py
```

### Success KPI emphasis
- rollback rate
- docs-to-adoption conversion

## Lane selection guidance

Choose the smallest lane that still meets your risk and compliance obligations.

| If your constraint is primarily… | Start in lane |
|---|---|
| Fast onboarding + value proof | Startup |
| Cross-team consistency | Scale |
| Audit readiness + strict escalation | Regulated |

## WS1 execution acceptance checklist

Use this checklist when executing **Point 2 (WS1 packaging execution)** in the CTO workflow.

- [x] Startup/Scale/Regulated lane definitions are published.
- [x] Each lane includes a command path and minimum controls.
- [x] KPI emphasis is declared per lane.
- [x] Role quickstarts are linked for execution by owner role.

Evidence links:

- [Role-based quickstarts](role-based-quickstarts.md)
- [Top-tier KPI schema](kpi-schema.md)
- [Top-tier program dashboard](top-tier-program-dashboard.md)
