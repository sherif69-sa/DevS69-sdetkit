# Security Gate

The `sdetkit security` command provides an offline-first, deterministic security control tower.

## Commands

- `python -m sdetkit security scan`
  - offline by default; runs secret scan, risky-pattern scan, offline dependency vuln scan, and CycloneDX SBOM generation.
- `python -m sdetkit security report --format sarif --output build/security.sarif`
  - exports SARIF 2.1.0 with stable rule IDs and remediation help text.
- `python -m sdetkit security check --baseline tools/security.baseline.json`
  - regression gate against a baseline.
- `python -m sdetkit security baseline --output tools/security.baseline.json`
  - writes a baseline snapshot.
- `python -m sdetkit security fix --dry-run`
  - safe deterministic fix preview with unified diff.
- `python -m sdetkit security fix --apply`
  - applies safe fixes only.

## Thresholds and exit codes

- `--fail-on none|low|medium|high|critical` (default: `medium`)
- exit code `0`: no finding at/above threshold
- exit code `1`: finding(s) at/above threshold
- exit code `2`: usage/config error

## Offline vs online

Offline is the default mode and never requires network. Optional online mode can be enabled with `--online`.
For online dependency scanning you can set `SDETKIT_SECURITY_ONLINE_CMD` to your organization-approved scanner command.

## Output formats

Use `--format text|json|sarif` and optional `--output <path>`.

- `text`: concise summary
- `json`: structured payload (`findings`, `counts`, `sbom`)
- `sarif`: GitHub code-scanning compatible

## Safe auto-fix scope

`security fix` currently auto-fixes conservative patterns only:

- `yaml.load(...)` -> `yaml.safe_load(...)`
- simple one-line requests timeout insertion

Not auto-applied:

- risky/ambiguous subprocess rewrites
- dynamic code execution transforms
