# Doctor

`doctor` is a repo health command focused on practical, release-ready diagnostics.

Run it via:

- `sdetkit doctor ...`
- `python -m sdetkit doctor ...`

Common usage:

```bash
sdetkit doctor --ascii
sdetkit doctor --all
sdetkit doctor --all --json
```

## What it checks

- `--ascii`: scans `src/` and `tools/` for non-ASCII bytes.
  - Skips `__pycache__/` and `.pyc` files.
- `--ci`: verifies required workflow files exist and validates YAML with pre-commit `check-yaml`.
- `--pre-commit`: validates pre-commit is installed and config is valid.
- `--deps`: runs `pip check` to detect dependency issues.
- `--clean-tree`: fails if `git status --porcelain` is not empty.
- `--dev`: validates local dev setup including required tools and active virtual environment.
- `--pyproject`: parses `pyproject.toml` early to catch TOML syntax issues before CI.

Convenience flags:

- `--all`: runs core checks in one command.
- `--release`: release-oriented check pack (`--all` + pyproject validation).

## Dev UX highlights

For local delivery checks you can run:

```bash
sdetkit doctor --dev --ci --deps --clean-tree
```

This now warns clearly if no virtual environment is active and provides concrete remediation.

## PR-ready output

Use `--pr` to print a compact markdown report that can be pasted directly into a PR comment:

```bash
sdetkit doctor --dev --ci --deps --clean-tree --pr
```

Use `--json` when integrating with bots or custom automation.

## Score and recommendations

Every run computes a `score` (0–100) from enabled checks and generates actionable `recommendations`.

- Human mode prints compact status + next steps.
- PR mode prints concise markdown.
- JSON mode includes `checks`, `score`, `recommendations`, and `ok`.

## Output and exit codes

- Exit code `0` means all enabled checks passed.
- Non-zero means at least one enabled check failed.
