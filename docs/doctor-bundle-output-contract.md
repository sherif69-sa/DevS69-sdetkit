# Doctor bundle output contract

This document records the expected output names for the Doctor artifact bundle.

## Base outputs

The base bundle should contain:

- `doctor-report.json`
- `doctor-report.md`
- `doctor-report-manifest.json`

## Extra output

When extra bundle input is provided, the artifact directory can also contain:

- `failure-vector.json`

## Stable ordering

When displaying or checking output names, keep this order:

1. `doctor-report.json`
2. `doctor-report.md`
3. `doctor-report-manifest.json`
4. `failure-vector.json`

## Unknown files

Unknown files in the artifact directory should not be treated as part of the Doctor bundle contract. Review them separately before a downstream consumer depends on them.

## Consumer rule

Downstream consumers should start with `doctor-report-manifest.json`, then read output paths from the manifest instead of assuming every file exists in every run.
