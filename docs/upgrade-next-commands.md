# Upgrade Next Commands (Intent -> Command)

Use this page when you know the goal but not the exact command.

## I need release confidence now

```bash
make first-proof
make first-proof-verify
make first-proof-freshness
```

Artifacts are produced under `build/first-proof/` and freshness can be contract-checked.

## I need a quick daily operator signal

```bash
make ops-now-lite
make ops-next
make doctor-remediate
```

This gives a deterministic follow-up decision, top next actions, and remediation hints when blockers exist.

## I need pre-merge safety checks

```bash
make ops-premerge-fast
make ops-premerge-next-fast
```

Use non-fast variants when you want the full lane:

```bash
make ops-premerge
make ops-premerge-next
```

## I need weekly reporting + governance posture

```bash
make ops-weekly
make top-tier-reporting
make plan-status
```

## I need one guided starting point

```bash
make upgrade-next
```

This prints the recommended "next 5 commands" sequence.

To run those five commands automatically:

```bash
UPGRADE_NEXT_RUN=1 make upgrade-next
```

The guided five-command lane includes:
- `first-proof-health-score` for an executive readiness score artifact (`build/first-proof/health-score.json`).
- `first-proof-freshness` to confirm first-proof artifacts remain current and auditable.
- `doctor-remediate` so the lane ends with top blocker fixes, not only status output.

To preview the exact sequence without executing:

```bash
UPGRADE_NEXT_RUN=1 UPGRADE_NEXT_DRY_RUN=1 make upgrade-next
```

## I need one-command onboarding-by-default

```bash
make operator-onramp
make operator-onramp-dry-run
make operator-onramp-verify
```

This runs `upgrade-next`, builds `onboarding-next` artifacts, and renders the first-proof dashboard.
`operator-onramp-verify` adds schema/execution/followup-ready contract checks.

## Notes

- Start from canonical deterministic gate path first: `gate fast` -> `gate release` -> `doctor`.
- Expand into advanced/phase commands only after first-proof is stable.

## I need contract trend visibility

```bash
make first-proof-ops-bundle-trend
```

This writes `build/first-proof/ops-bundle-contract-trend.json` and updates history JSONL.

## I need one final operator summary

```bash
make first-proof-execution-report
```

This writes `build/first-proof/execution-report.json` and `execution-report.md`.

## I need a strict final contract gate

```bash
make first-proof-execution-contract
```

This verifies key fields across final first-proof execution artifacts.

## I need one-line CI/operator status

```bash
make upgrade-status-line
```

Writes `build/first-proof/upgrade-status-line.txt` for quick scanning.

## I need final follow-up readiness gate

```bash
make first-proof-followup-ready
```

This verifies execution contract + summary outputs needed for operator handoff.

## I need retention cleanup (TTL)

```bash
make cleanup-first-proof-artifacts
```

Default is dry-run with a 168-hour TTL and JSON report output.

## I need CI artifact publishing

Use workflow: `.github/workflows/first-proof-artifact-publish.yml`

It publishes execution report + status line + follow-up artifacts from `first-proof-verify-local`.

## I need remediation-time metrics

```bash
make followup-ready-metrics
```

Writes follow-up history and `median_time_to_remediate_hours`.

## I need weekly ops-bundle trend markdown

```bash
make first-proof-ops-bundle-trend-report
```

Writes `build/first-proof/ops-bundle-contract-trend.md`.

## I need branch-specific trend splits

`first-proof-ops-bundle-trend` now tracks branch-specific pass-rate fields using `FIRST_PROOF_BRANCH` in Makefile.

## I need schema consistency checks

```bash
make first-proof-schema-contract
```

Validates `schema_version` across key first-proof artifacts.

## I need consolidated first-proof dashboard

```bash
make first-proof-dashboard
```

Writes `build/first-proof/dashboard.json` and `dashboard.md`.

## I need follow-up changelog automation

```bash
make followup-changelog
```

Appends run-level summary entries to `build/first-proof/followup-changelog.jsonl`.

## I need profile-based readiness threshold gate

```bash
make first-proof-readiness-threshold
```

Uses `FIRST_PROOF_READINESS_PROFILE` with profiles in `config/first_proof_readiness_profiles.json`.
