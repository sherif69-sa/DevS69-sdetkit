# Repo Audit

`sdetkit repo audit` provides deterministic, file-system-only repository readiness checks suitable for local development and CI.

## Quick start

```bash
sdetkit repo audit
sdetkit repo audit --format json --out repo-audit.json --force
```

## Checks performed (`sdetkit repo audit`)

- **OSS readiness files**: checks for `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, and `CHANGELOG.md`.
- **CI/Security workflow presence**: verifies `.github/workflows/` includes at least one CI workflow and one security-focused workflow.
- **Python tooling config**: verifies key Python project files are present (`pyproject.toml`, `noxfile.py`, `quality.sh`, `requirements-test.txt`).
- **Basic repo hygiene**: checks for `.gitignore`, `tests/`, `docs/`, and flags oversized tracked files (>5 MiB).

All checks are deterministic and local-only (no network calls).

## Output formats

- `--format text` (default): human-readable summary with pass/fail details.
- `--format json`: machine-readable report suitable for CI artifacts and policy engines.

Example JSON run:

```bash
sdetkit repo audit --format json
```

## Exit codes

- `0`: clean / policy pass
- `1`: one or more audit checks failed
- `2`: invalid usage, unsafe path, or internal/runtime error

## Complementary commands

- `sdetkit repo check`: deep content scanning and risk-focused findings.
- `sdetkit repo fix`: safe, idempotent whitespace/EOL normalization.

Use `repo audit` for release-readiness snapshots, and `repo check`/`repo fix` for detailed hygiene remediation.
