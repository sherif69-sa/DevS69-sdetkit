# Governance and org packs

`sdetkit repo audit` supports governed allowlist exceptions and organization policy packs.

## Governed allowlist entries

Use TOML tables for deterministic, reviewable exceptions:

```toml
[[tool.sdetkit.repo_audit.allowlist]]
rule_id = "CORE_MISSING_SECURITY_MD"
path = "SECURITY.md"
contains = "missing required file"
owner = "security@acme.example"
justification = "Temporary exception while template is being migrated"
created = "2026-01-01"
expires = "2026-06-30"
ticket = "SEC-1234"
```

Fields:

- `owner` (required by lint)
- `justification` (required by lint, non-empty)
- `created` (optional ISO date)
- `expires` (optional ISO date)
- `ticket` (optional)
- `rule_id`, `path`, `contains` (match scope)

## Expiration and determinism

Current date source:

1. `SDETKIT_TODAY=YYYY-MM-DD` if set (recommended for CI/tests)
2. Local date otherwise

Behavior:

- `expires < today` → entry is `expired`
- Expired entries do **not** suppress findings
- Expired matches are reported in audit summaries via `suppressed_expired`

## Policy lint (CI-friendly)

```bash
sdetkit repo policy lint . --format json --fail-on warn
```

Checks include:

- missing `owner` / `justification` (errors)
- expired exceptions (warning)
- exceptions too far in future (warning, default threshold 365 days via `lint_expiry_max_days`)
- duplicate allowlist scope tuples
- unknown rule IDs in `disable_rules` and `severity_overrides`
- unknown selected org packs

## Policy export artifact

```bash
sdetkit repo policy export . --output policy-artifact.json --include-expired
```

Export format:

- `schema_version: "sdetkit.policy.v1"`
- normalized allowlist entries
- computed `status` (`active` / `expired`)
- deterministic ordering and stable JSON keys

Use this artifact in CI for human approval workflows.

## Org packs

Select org packs from CLI or config:

```toml
[tool.sdetkit.repo_audit]
org_packs = ["org-acme", "org-platform"]
```

```bash
sdetkit repo audit . --org-pack org-acme --org-pack org-platform
```

Entry point group for pack plugins:

- `sdetkit.repo_audit_packs`

Plugin contract:

- `pack_name: str`
- `rule_ids: list[str] | tuple[str, ...]`
- optional `defaults`:
  - `fail_on`
  - `severity_overrides`

Org packs add rule selection and can provide defaults, while core rule IDs remain explicit and auditable.
