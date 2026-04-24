# Dependency SLO policy (Phase 3)

This policy defines when dependency drift is advisory vs blocking for CI/routing.

## SLO intent

- Keep upgrade pressure visible without generating noisy failures.
- Fail only on policy-critical drift in automated lanes.
- Preserve a weekly operator rhythm for medium/low-priority drift.

## Threshold policy

Policy source of truth: `config/dependency_slo_policy.json`.

Current defaults:

- `critical_upgrade_signals`: max **0** (fail when any critical signal exists)
- `high_priority_upgrade_signals`: max **2**
- `actionable_packages`: max **12**

## Artifact + check flow

1. Generate upgrade audit payload (`upgrade_audit` JSON).
2. Build radar artifact with threshold evaluation via `scripts/phase3_dependency_radar.py`.
3. Fail only when `breach == true` and lane is configured with `--fail-on-breach`.

## Weekly operations

- Open/refresh weekly drift issue using `.github/ISSUE_TEMPLATE/dependency-drift-weekly.yml`.
- Attach latest radar artifact and top priority queue entries.
