# GitHub Action: `sdetkit repo audit`

Use the composite action at `.github/actions/repo-audit` to run a deterministic `sdetkit repo audit` in CI with optional SARIF upload, Step Summary output, and JSON artifact export.

## Reuse from another repository

Copy the action folder into your repository (or vendor it through your internal templates), then add a workflow like this:

```yaml
name: Repo Audit

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  security-events: write

jobs:
  repo-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: ./.github/actions/repo-audit
        with:
          path: .
          profile: default
          fail_on: ${{ github.event_name == 'pull_request' && 'warn' || 'error' }}
          write_summary: true
          output_json: true
          upload_json: true
          upload_sarif: true
```

> Installation strategy: the action first tries `pip install sdetkit` from PyPI. If that is unavailable, it falls back to editable install from the checked-out workspace (`$GITHUB_WORKSPACE`) or the requested audit path when a `pyproject.toml` is present. If neither source is available, the action fails with a clear error.

## Inputs

- `path` (`.`): target path for `sdetkit repo audit`.
- `profile` (`default`): audit profile (`default` or `enterprise`).
- `fail_on` (`warn`): failure threshold (`none`, `warn`, `error`).
- `python_version` (`3.12`): Python runtime for the action.
- `upload_sarif` (`true`): upload SARIF to GitHub Code Scanning.
- `sarif_path` (`sdetkit-audit.sarif.json`): SARIF output file path.
- `write_summary` (`true`): append markdown to Step Summary.
- `output_json` (`true`): generate JSON output file.
- `json_path` (`sdetkit-audit.json`): JSON output file path.
- `upload_json` (`true`): upload JSON report as workflow artifact.
- `json_artifact_name` (`sdetkit-audit-json`): artifact name for JSON report.

## Permissions

If `upload_sarif: true`, the workflow needs:

```yaml
permissions:
  contents: read
  security-events: write
```

## Step Summary

When `write_summary: true`, the action appends a markdown report to `$GITHUB_STEP_SUMMARY` that includes:

- profile and `fail_on`
- severity counts (`info`, `warn`, `error`)
- top findings table (up to 10 items)
- hints for Code Scanning and JSON artifact location

In GitHub UI, open the workflow run, then open the job to view the **Step Summary** panel.

## JSON artifact details

When `output_json: true` and `upload_json: true`, the report is uploaded as an artifact (default: `sdetkit-audit-json`). Download it from the workflow run artifacts section.

The JSON payload includes `schema_version` plus `summary`, `checks`, and `findings`, so downstream tooling can parse it deterministically.
