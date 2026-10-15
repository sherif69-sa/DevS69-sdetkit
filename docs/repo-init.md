# Repo init

`sdetkit init` (also `sdetkit repo init`) writes baseline CI workflows and governance files into a repository, offline and deterministically.

## Command

```bash
sdetkit init [--root PATH] [--preset enterprise_python] [--dry-run] [--diff] [--force] [--write-config] [--format text|json]
```

- `--root` is the repository to set up: any directory, absolute or relative (for example `--root ../service`). Defaults to `.`.
- `--preset` defaults to `enterprise_python`, currently the only preset.
- **init writes by default.** Pass `--dry-run` to print the plan without writing anything, and add `--diff` to see the content.
- `--write-config` also creates `.sdetkit/config.toml` if it is missing.
- `--format json` adds the detected repository facts and the next commands to run.

## Files

The `enterprise_python` preset plans these files:

- `.github/workflows/ci.yml`
- `.github/workflows/quality.yml`
- `.github/workflows/security.yml`
- `CODEOWNERS`
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `LICENSE`
- `SECURITY.md`

## Safety rules

- Every file is written inside `--root`; files are planned in sorted order.
- Existing files are **never overwritten** without `--force`. If an existing file differs, `init` writes nothing and exits `2`, naming each file.
- `sdetkit repo apply --preset enterprise_python` uses the same plan but skips differing files instead of stopping.
- Writes are atomic.

## Examples

Preview the plan and the content:

```bash
sdetkit init --dry-run --diff
```

Set up another repository:

```bash
sdetkit init --root ../service
```

Overwrite files that differ from the preset:

```bash
sdetkit init --force
```

## Idempotency

Running `sdetkit init` again once the files match the preset plans no changes.
