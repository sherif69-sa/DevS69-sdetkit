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

- **CodeQL scanning** (`security.yml`) runs on push, pull requests, and schedule.
- **Dependabot** checks Python and GitHub Actions dependencies daily.
- **Dependabot auto-merge** (`dependency-auto-merge.yml`) is enabled for **minor/patch** updates after checks pass.
- **Secret scanning bot** (gitleaks inside `security-maintenance-bot.yml`) uploads SARIF to GitHub code scanning.
- **OSV vulnerability scanning** (`osv-scanner.yml`) runs daily and uploads SARIF into code scanning.
- **Dependency Audit** (`dependency-audit.yml`) runs `pip-audit` against the repo dependency surface.
- **SBOM refresh** (`sbom.yml`) keeps dependency inventory artifacts current for downstream review.
- **GHAS review bot** (`ghas-review-bot.yml`) creates a weekly digest issue for code scanning, Dependabot, secret scanning, workflow freshness, and campaign follow-up prompts.
- **GHAS campaign bot** (`ghas-campaign-bot.yml`) creates a weekly planner issue for Copilot Autofix-aware code scanning campaigns, secret scanning age buckets, and push-protection follow-up.
- **GHAS alert SLA bot** (`ghas-alert-sla-bot.yml`) creates a weekly issue that tracks 7/14/30-day backlog breaches across code scanning, Dependabot, and secret scanning.
- **GHAS metrics export bot** (`ghas-metrics-export-bot.yml`) exports a reusable `ghas-metrics.json` artifact and opens a weekly metrics snapshot issue for dashboards and audits.
- **Security configuration audit bot** (`security-configuration-audit-bot.yml`) runs monthly to audit repo-local GHAS workflow coverage, code security configuration visibility, and dependency submission posture.
- **Dependency review gate** (`dependency-review.yml`) blocks pull requests that introduce high-severity dependency risk or denied licenses.
- **Weekly maintenance issue** (`security-maintenance-bot.yml`) is refreshed automatically with checklist items, weak-spot reports, and links.
- **Dependency radar bot** (`dependency-radar-bot.yml`) publishes a recurring upgrade radar and runtime fast-follow watchlist.
- **Pre-commit hooks auto-update** (`pre-commit-autoupdate.yml`) runs weekly and opens a maintenance PR.

Use the GitHub Security tab to review alerts:

- Code scanning: `https://github.com/sherif69-sa/DevS69-sdetkit/security/code-scanning`
- Dependabot alerts: `https://github.com/sherif69-sa/DevS69-sdetkit/security/dependabot`

## Security Control Tower modes

See [security-gate.md](security-gate.md) for offline-first scan/report/fix behavior, optional online scanning, and SARIF output.
