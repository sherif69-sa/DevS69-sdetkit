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

The repository runs these security workflows (all in `.github/workflows/`):

- **CodeQL scanning** (`security.yml`) runs on pushes, pull requests and weekly.
- **OSV vulnerability scanning** (`osv-scanner.yml`) runs daily and uploads SARIF to code scanning.
- **Dependency audit** (`dependency-audit.yml`) runs `pip-audit` against the requirement files daily.
- **Dependency review** (`dependency-review.yml`) blocks pull requests that add high-severity vulnerabilities or denied licenses.
- **SBOM** (`sbom.yml`) builds the CycloneDX software bill of materials on every push to `main`.
- **Dependabot** (`.github/dependabot.yml`) proposes Python and GitHub Actions updates, and **dependency auto-merge** (`dependency-auto-merge.yml`) merges minor and patch updates once checks pass, after refreshing `uv.lock`.
- **Pre-commit autoupdate** (`pre-commit-autoupdate.yml`) opens a weekly pull request for hook updates.
- **Maintenance autopilot** (`maintenance-autopilot.yml`) runs the maintenance checks daily and on pull requests.
- **Branch protection** (`enforce-branch-protection.yml`) checks weekly that `main` keeps its required checks.

Use the GitHub Security tab to review alerts:

- Code scanning: `https://github.com/sherif69-sa/DevS69-sdetkit/security/code-scanning`
- Dependabot alerts: `https://github.com/sherif69-sa/DevS69-sdetkit/security/dependabot`

## Security Control Tower modes

See [security-gate.md](security-gate.md) for offline-first scan/report/fix behavior, optional online scanning, and SARIF output.

## GHAS tracker collection semantics

Security trackers distinguish an **authoritative zero** from an **unknown**
collection state:

- **Authoritative zero** means the relevant GitHub security API responded
  successfully with a valid empty alert array.
- **Unknown** means the API was unavailable, access was denied, or the response
  payload was not a valid alert array.
- Any age bucket, severity slice, bypass count, or other derived metric remains
  `unknown` when its source collection is unknown.
- Tracker issues include source-specific collection status so operators can
  distinguish a current empty queue from incomplete evidence.
- Workflow freshness is cadence-aware; the monthly security-configuration
  audit uses a 35-day maximum age rather than the weekly 14-day threshold.

These workflows are reporting surfaces. Their output does not authorize alert
dismissal, security-configuration mutation, workflow reruns, patch automation,
merge, or semantic-equivalence claims.
