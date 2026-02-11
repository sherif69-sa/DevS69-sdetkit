# Repo init

`repo init` bootstraps baseline governance and GitHub templates for a repository in a deterministic, offline-safe way.

## Command

```bash
sdetkit repo init [PATH] [--profile default|enterprise] [--dry-run] [--apply] [--force] [--diff]
```

- `PATH` defaults to `.`.
- `--profile` defaults to `default`.
- **Safe default behavior is dry-run**: if `--apply` is not provided, the command only prints a plan.

## Safety rules

- Files are planned in deterministic sorted order.
- Existing files are **never overwritten** unless `--force` is provided.
- If a file exists and content differs, init exits non-zero (`2`) unless `--force` is set.
- Writes use atomic file replacement and safe path checks.

## Profiles

### default

Creates these files when missing:

- `SECURITY.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `.github/ISSUE_TEMPLATE/config.yml`
- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `.github/PULL_REQUEST_TEMPLATE.md`

### enterprise

Includes everything from `default`, plus:

- `.github/dependabot.yml`
- `.github/workflows/quality.yml`
- `.github/workflows/security.yml`

## Examples

Plan changes only (default behavior):

```bash
sdetkit repo init
```

Explicit dry-run with unified diffs:

```bash
sdetkit repo init . --dry-run --diff
```

Apply default profile changes:

```bash
sdetkit repo init . --apply
```

Apply enterprise profile and allow deterministic overwrites:

```bash
sdetkit repo init . --profile enterprise --apply --force
```

## Idempotency

Running `repo init --apply` repeatedly is idempotent: once templates are present with matching content, the command reports no changes.
