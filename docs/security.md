# Security hardening

## Threat model (practical)

`sdetkit` CLI commands are often run in CI/CD or developer machines where:

- secrets are passed in headers/query/body,
- untrusted input can influence output paths,
- network targets can be malformed or hostile.

The primary risks are secret leakage, unsafe outbound requests, and unsafe file writes.

## Secure defaults

- **Redaction on by default** for printed request/response metadata.
- **HTTP timeout required** via explicit client defaults (no infinite wait).
- **Scheme allowlist** defaults to `http`/`https` only.
- **Redirect handling explicit** and conservative by default.
- **TLS verify on by default**.
- **Path safety checks** reject NUL bytes, traversal, and absolute paths unless explicitly allowed.
- **Atomic file writes** for generated artifacts to prevent partial writes.
- **No overwrite by default** for output artifacts unless `--force` is supplied.

## Opt out safely

Only opt out when necessary and scoped:

- `--no-redact` only for local debugging and never in shared CI logs.
- `--allow-scheme ...` only for trusted internal protocols and explicit environments.
- `--insecure` only in controlled test environments with isolated traffic.
- `--force` only when overwrite is expected and reviewed.

## Exit codes

- `0`: success
- `1`: expected negative result (for example, `patch --check` found changes needed; doctor checks failed)
- `2`: invalid usage/config, unsafe path, or runtime error

## Continuous security automation

The repository includes always-on security maintenance so it behaves like an auto-update system:

- **CodeQL scanning** runs on push, pull requests, and schedule.
- **Dependabot** checks Python and GitHub Actions dependencies daily.
- **Dependabot auto-merge** is enabled for **minor/patch** updates after checks pass.
- **Secret scanning bot** runs daily using gitleaks and uploads SARIF to GitHub code scanning.
- **Weekly maintenance issue** is refreshed automatically with checklist items and links.
- **OSV vulnerability scanning** runs daily and uploads SARIF into code scanning.
- **Pre-commit hooks auto-update** runs weekly and opens a maintenance PR.

Use the GitHub Security tab to review alerts:

- Code scanning: `https://github.com/sherif69-sa/sdet_bootcamp/security/code-scanning`
- Dependabot alerts: `https://github.com/sherif69-sa/sdet_bootcamp/security/dependabot`
