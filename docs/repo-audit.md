# Repo Audit

`sdetkit repo audit` provides deterministic, file-system-only repository readiness checks suitable for local development and CI.

## Quick start

```bash
sdetkit repo audit
sdetkit repo audit --format json --output repo-audit.json --force
```

## Performance: cache strategy

Repo audit writes a local cache under `.sdetkit/cache` to speed up repeated runs. The default `--cache-strategy tree` invalidates cached results when tracked files change. Use `--cache-strategy deps` to reuse per-rule results when the files a rule depends on are unchanged.

```bash
sdetkit repo audit --cache-stats
sdetkit repo audit --cache-strategy deps --cache-stats
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
- `--format sarif`: SARIF 2.1.0 output for code scanning ingestion.

Example JSON run:

```bash
sdetkit repo audit --format json
```

Example SARIF run:

```bash
sdetkit repo audit --format sarif --output repo-audit.sarif --force
```

Fail policy examples:

```bash
# never fail CI from audit findings
sdetkit repo audit --fail-on none

# fail when warn/error findings exist (default)
sdetkit repo audit --fail-on warn

# fail only on error findings
sdetkit repo audit --fail-on error
```

## Exit codes

- `0`: policy pass for selected `--fail-on` threshold
- `1`: threshold hit by findings per `--fail-on`
- `2`: invalid usage, unsafe path, or internal/runtime error

## Complementary commands

- `sdetkit repo check`: deep content scanning and risk-focused findings.
- `sdetkit repo fix`: safe, idempotent whitespace/EOL normalization.

Use `repo audit` for release-readiness snapshots, and `repo check`/`repo fix` for detailed hygiene remediation.
