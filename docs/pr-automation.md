# PR automation for audit auto-fixes

`repo pr-fix` turns `repo fix-audit` results into a deterministic local branch and optional GitHub pull request.

## Local branch workflow (offline)

```bash
sdetkit repo pr-fix . --apply
```

Default behavior:

- Uses branch `sdetkit/fix-audit`.
- Uses current branch as `--base-ref`.
- Commits automatically when `--apply` is set (use `--no-commit` to disable).
- Fails if the branch already exists unless `--force-branch` is set.
- If no changes are needed, prints `no changes` and exits `0`.

Deterministic commit metadata:

- If `SOURCE_DATE_EPOCH` is set, commit author/committer date uses that value.
- Commit message defaults to a stable template including sorted rule IDs and file count.

## Patch-only workflow

```bash
sdetkit repo pr-fix . --dry-run --diff --patch out.patch --force
```

This reuses the same fix planner while keeping work offline and without branch/commit operations.

## Open a PR on GitHub (explicit opt-in)

Network access is only used when `--open-pr` is provided.

```bash
export GITHUB_TOKEN=...
sdetkit repo pr-fix . --apply --open-pr --remote origin
```

Options:

- `--repo OWNER/NAME` overrides remote autodetection.
- `--title`, `--body`, `--body-file` override generated PR text.
- `--draft` creates a draft PR.
- `--labels "a,b,c"` applies labels after PR creation.

Token guidance:

- Default token variable is `GITHUB_TOKEN` (`--token-env` to override).
- Token needs permission to push branch and create PRs (plus labels if used).
- Missing token exits with code `2` and a clear error.

## Monorepo examples

Single project:

```bash
sdetkit repo pr-fix . --project service-a --apply
```

All projects:

```bash
sdetkit repo pr-fix . --all-projects --sort --apply
```

Generated PR body includes deterministic per-project breakdown (rules and file counts).
