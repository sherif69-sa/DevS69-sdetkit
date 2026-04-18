# Operator essentials (Phase 2 surface-clarity baseline)

This page is the intentionally small command subset for day-to-day release-confidence operations.

If a team is new to SDETKit, start here first and expand only after this lane is trusted.

## Tier 0 — First-run canonical path (always first)

1. `python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json`
2. `python -m sdetkit gate release --format json --out build/release-preflight.json`
3. `python -m sdetkit doctor`

Expected first artifacts:

- `build/gate-fast.json`
- `build/release-preflight.json`

## Tier 1 — Core operational follow-up

Use these after Tier 0 when you need remediation and operational triage depth:

- `python -m sdetkit review . --no-workspace --format operator-json`
- `python -m sdetkit doctor --enterprise --format md`
- `python -m sdetkit doctor --enterprise-next-pass-only --enterprise-next-pass-exit-code`

## Tier 2 — Team rollout and CI alignment

- `python scripts/validate_enterprise_contracts.py`
- `python scripts/check_primary_docs_map.py`
- `make phase1-baseline`
- `make phase2-surface-clarity`
- `make phase3-quality-contract`
- `make phase4-governance-contract`
- `make phase5-ecosystem-contract`
- `make phase6-metrics-contract`

## Expansion trigger rules

Expand beyond this page only when all of the following are true:

1. Tier 0 commands are deterministic in local and CI.
2. Release artifacts are being reviewed before raw logs.
3. Blockers are triaged from machine-readable fields (`ok`, `failed_steps`) first.

## Next-step expansion map

After operator essentials is stable, expand in this order:

1. `kits` discovery and umbrella lanes (`release`, `intelligence`, `integration`, `forensics`)
2. advanced inspection lanes (`inspect`, `inspect-compare`, `inspect-project`)
3. migration/legacy compatibility lanes (only when required)
