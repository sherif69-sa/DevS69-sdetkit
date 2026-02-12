# Reporting and trends

`sdetkit repo audit` can emit a stable run record (`sdetkit.audit.run.v1`) to support enterprise reporting, deltas, and drift tracking.

## Run record (v1)

Use:

- `sdetkit repo audit --format json --json-schema v1`
- `sdetkit repo audit --emit-run-record run.json`

Record highlights:

- deterministic finding ordering and key ordering
- stable fingerprints per finding
- aggregate counters (severity, suppressed, fixable)
- optional source metadata (`GITHUB_SHA`, `SOURCE_DATE_EPOCH`)

## Ingest history

```bash
sdetkit report ingest run.json --history-dir .sdetkit/audit-history --label "main"
```

Behavior:

- validates/normalizes to run-record v1
- stores run under SHA-256 content filename
- updates `.sdetkit/audit-history/index.json`
- idempotent for duplicate runs

## Diff two runs

```bash
sdetkit report diff --from old.json --to new.json --format text --fail-on warn
```

Diff uses finding fingerprint sets and reports:

- NEW
- RESOLVED
- UNCHANGED

Exit codes:

- `0`: no NEW findings at/above threshold
- `1`: NEW findings at/above threshold
- `2`: usage/parse errors

## Build dashboard

```bash
sdetkit report build --history-dir .sdetkit/audit-history --output report.html --format html
sdetkit report build --history-dir .sdetkit/audit-history --output report.md --format md --since 20
```

Dashboard is deterministic and offline-friendly:

- latest run snapshot
- delta vs previous run
- simple trend sparkline/table data
- top recurring rules and paths

## CI / GitHub summary integration

`repo audit` additions:

- `--emit-run-record PATH`
- `--diff-against PATH`
- `--step-summary` (writes markdown to `GITHUB_STEP_SUMMARY` when set)

Summary content includes:

- total/suppressed/actionable counts
- NEW/RESOLVED when `--diff-against` is used
- top 10 actionable findings
- fix hint: `sdetkit repo fix-audit --dry-run`

## History storage strategy

You can keep history:

- in-repo (`.sdetkit/audit-history`) for local trend review, or
- as CI artifacts (for lighter repos and cleaner history ownership)

Phase 3 GitHub Action JSON artifacts are compatible with `sdetkit report ingest` because legacy audit JSON is normalized to v1 on ingest.
