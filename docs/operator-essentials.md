# Operator essentials

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
- `python -m sdetkit investigate failure --log build/quality.log --format markdown`
- `python -m sdetkit investigate repo --root . --format json --out build/investigation/repo.json`
- `python -m sdetkit investigate surface --root . --surface <surface> --format markdown`
- `python -m sdetkit doctor --enterprise --format md`
- `python -m sdetkit doctor --enterprise-next-pass-only --enterprise-next-pass-exit-code`

See [Investigation operator guide](investigation-operator-guide.md) for the diagnostic-only investigation flow and safety interpretation, and [Artifact reference and generated sample map](artifact-reference.md) for the runtime/uploaded artifact paths. The investigate commands recommend proof and next actions only; they do not approve mutation.

## Tier 2 — Team rollout and CI alignment

- `python scripts/validate_enterprise_contracts.py`
- `python scripts/check_primary_docs_map.py`
- `make phase1-baseline`
- `make phase1-status`
- `make phase1-next`
- `make phase1-complete`
- `make phase2-start`
- `make phase2-workflow`
- `make phase2-status`
- `make phase2-start-contract`
- `make phase2-seed`
- `make phase2-complete`
- `make phase2-progress`
- `make phase2-surface-clarity`
- `make phase3-quality-contract`
- `make phase4-governance-contract`
- `make phase5-ecosystem-contract`
- `make phase6-start`
- `make phase6-status`
- `make phase6-progress`
- `make phase6-complete`
- `make phase6-metrics-contract`

`make phase2-workflow` runs strict kickoff + contract checks and writes summary artifacts under `build/phase2-start/`.
`make phase2-status` reports whether emitted Phase 2 kickoff artifacts are complete and contract-valid.
`make phase2-start-contract` validates the generated summary contract (`phase2-start-summary.json`).
`make phase2-seed` writes minimum prerequisite inputs so strict Phase 2 lanes can run in a fresh workspace.
`make phase2-complete` runs startup + hardening closeout + wrap-handoff closeout in one executable chain.
`make phase2-progress` reports % completion and milestone coverage for Phase 2 closeout.
`make phase2-start` is the rollout alias for `make phase2-workflow`.

## Expansion trigger rules

Expand beyond this page only when all of the following are true:

1. Tier 0 commands are deterministic in local and CI.
2. Release artifacts are being reviewed before raw logs.
3. Blockers are triaged from machine-readable fields (`ok`, `failed_steps`) first.

## Next-step expansion map

After operator essentials is stable, expand in this order:

1. Investigation and diagnosis: [Investigation operator guide](investigation-operator-guide.md) -> [Adaptive Diagnosis Intelligence](adaptive-diagnosis.md) -> [Remediation cookbook](remediation-cookbook.md).
2. Artifact interpretation: [Artifact reference and generated sample map](artifact-reference.md) -> [CI artifact walkthrough](ci-artifact-walkthrough.md).
3. Quality gates: [Premium quality gate](premium-quality-gate.md) -> [Security gate](security-gate.md) -> [Determinism checklist](determinism-checklist.md).
4. `kits` discovery and umbrella lanes (`release`, `intelligence`, `integration`, `forensics`).
5. Advanced inspection lanes (`inspect`, `inspect-compare`, `inspect-project`).
6. Migration/legacy compatibility lanes (only when required).

Keep the safety boundary intact while expanding: diagnose -> recommend -> plan -> prove can happen by default; candidate, probation, policy proposal, dry run, guarded PR auto-fix, and memory updates require the documented guarded lanes and review posture.
