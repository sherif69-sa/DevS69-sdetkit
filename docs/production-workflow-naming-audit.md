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

Avoid adding new workflow names that read like internal sequencing or operator guidance labels:

- baseline stage, release readiness stage, platform readiness stage
- do-it
- completion report
- completion signal
- deprecation plan
- follow-up pass
- release readiness gate

## Compatibility approach

Do not break existing automation by removing old Make targets. Add production-name aliases first, then migrate workflows and docs gradually.

## Initial alias map

| Production alias | Compatibility target |
|---|---|
| `quality-contract-check` | `platform-readiness-quality-contract` |
| `quality-contract-report` | `platform-readiness-quality-report` |
| `quality-contract-run` | `platform-readiness-quality-run` |
| `operations-baseline` | `baseline-foundation` |
| `operations-status` | `baseline-status` |
| `operations-next-action` | `baseline-next-action` |
| `operations-snapshot` | `baseline-ops-snapshot` |
| `operations-dashboard` | `baseline-dashboard` |
| `operations-weekly-pack` | `baseline-weekly-pack` |
| `operations-control-loop` | `baseline-control-loop` |
| `operations-run-all` | `baseline-run-all` |
| `operations-artifact-set` | `baseline-artifact-set` |
| `operations-telemetry` | `baseline-telemetry` |
| `operations-readiness-signal` | `baseline-readiness-signal` |
| `operations-remediation-plan` | `baseline-followup-pass` |
| `operations-blocker-register` | `baseline-blocker-register` |
| `operations-run` | `baseline-run` |
| `operations-core-run` | `baseline-execution-core` |
| `operations-workflow` | `baseline-workflow` |
| `operations-flow-contract` | `baseline-flow-contract` |
| `operations-quality-gate` | `baseline-release-readiness-gate` |
| `operations-executive-report` | `baseline-executive-report` |
| `operations-cleanup-plan` | `baseline-transition-plan` |
| `operations-complete` | `baseline-complete` |
| `operations-finalize` | `baseline-completion-report` |
| `operations-current` | `operations-current-status` |
| `operations-current-json` | `operations-current-status-json` |
| `governance-contract-check` | `operational-readiness-governance-contract` |
| `ecosystem-contract-check` | `adoption-readiness-ecosystem-contract` |
| `metrics-contract-check` | `scale-readiness-metrics-contract` |
