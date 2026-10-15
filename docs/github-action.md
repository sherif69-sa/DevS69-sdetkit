# GitHub Action: `sdetkit repo audit`

Use the composite action at `.github/actions/repo-audit` to run a deterministic `sdetkit repo audit` in CI with optional SARIF upload, Step Summary output, and JSON artifact export.

## Which action do I use?

| Action | Answers | Reports to |
| --- | --- | --- |
| [SDETKit gate](gate-action.md) (`uses: sherif69-sa/DevS69-sdetkit@…`) | Is this change ready to ship? Runs your lint, types and tests, and returns one verdict. | Job summary, one pull request comment, step result |
| `sdetkit repo audit` (this page) | Is the repository set up well? Checks governance files, configuration and hygiene. | Code scanning (SARIF), job summary, JSON artifact |

Most repositories want the gate on every pull request. Add the repo audit when you also want hygiene findings in GitHub code scanning.

## Use it from another repository

Check the repository out, then call the action by path and version:

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
      - uses: actions/checkout@v4
      - uses: sherif69-sa/DevS69-sdetkit/.github/actions/repo-audit@v2.0.0
        with:
          path: .
          profile: default
          fail_on: ${{ github.event_name == 'pull_request' && 'warn' || 'error' }}
          write_summary: true
          output_json: true
          upload_json: true
          upload_sarif: true
```

!!! note "Before 2.0.0 is tagged"
    Until the `v2.0.0` tag exists, use `@main`, or pin a commit SHA from `main`.

**Installation:** the action installs sdetkit from its own source, the version you reference, into a separate virtual environment. Your project and its dependencies are not installed or changed. To install a release from PyPI instead, set `sdetkit_version`. The action does not check the repository out itself; run `actions/checkout` first.

## Inputs

- `path` (`.`): target path for `sdetkit repo audit`.
- `profile` (`default`): audit profile (`default` or `enterprise`).
- `fail_on` (`warn`): failure threshold (`none`, `warn`, `error`).
- `python_version` (`3.12`): Python runtime for the action.
- `sdetkit_version` (empty): install this sdetkit version from PyPI instead of the action's own source.
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
