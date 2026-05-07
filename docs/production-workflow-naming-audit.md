# Production workflow naming audit

This repo still carries some internal phase-style workflow names. Those names remain available for compatibility, but new commands, docs, PR titles, branches, and tests should use production workflow language.

## Naming direction

Prefer production workflow names:

- quality contract
- operations status
- operations readiness
- operations completion
- cleanup plan
- remediation plan
- governance contract
- ecosystem contract
- metrics contract

Avoid adding new workflow names that read like internal sequencing or education labels:

- phase1, phase2, phase3
- do-it
- closeout
- finish-signal
- retire-plan
- next-pass
- gate-phase2

## Compatibility approach

Do not break existing automation by removing old Make targets. Add production-name aliases first, then migrate workflows and docs gradually.

## Initial alias map

| Production alias | Compatibility target |
|---|---|
| `quality-contract-check` | `phase3-quality-contract` |
| `quality-contract-report` | `phase3-quality-report` |
| `quality-contract-run` | `phase3-do-it` |
| `operations-baseline` | `phase1-baseline` |
| `operations-status` | `phase1-status` |
| `operations-next-action` | `phase1-next` |
| `operations-snapshot` | `phase1-ops-snapshot` |
| `operations-dashboard` | `phase1-dashboard` |
| `operations-weekly-pack` | `phase1-weekly-pack` |
| `operations-control-loop` | `phase1-control-loop` |
| `operations-run-all` | `phase1-run-all` |
| `operations-artifact-set` | `phase1-artifact-set` |
| `operations-telemetry` | `phase1-telemetry` |
| `operations-readiness-signal` | `phase1-finish-signal` |
| `operations-remediation-plan` | `phase1-next-pass` |
| `operations-blocker-register` | `phase1-blocker-register` |
| `operations-run` | `phase1-do-it` |
| `operations-core-run` | `phase1-execution-core` |
| `operations-workflow` | `phase1-workflow` |
| `operations-flow-contract` | `phase1-flow-contract` |
| `operations-quality-gate` | `phase1-gate-phase2` |
| `operations-executive-report` | `phase1-executive-report` |
| `operations-cleanup-plan` | `phase1-retire-plan` |
| `operations-complete` | `phase1-complete` |
| `operations-finalize` | `phase1-closeout` |
| `operations-current` | `phase-current` |
| `operations-current-json` | `phase-current-json` |
| `governance-contract-check` | `phase4-governance-contract` |
| `ecosystem-contract-check` | `phase5-ecosystem-contract` |
| `metrics-contract-check` | `phase6-metrics-contract` |
