# Policy-as-Code

`policy` is a governance-grade regression control surface around security + hygiene drift.

## Commands

- `sdetkit policy snapshot --output .sdetkit/policies/baseline.json`
- `sdetkit policy check --baseline .sdetkit/policies/baseline.json --format json`
- `sdetkit policy diff --baseline .sdetkit/policies/baseline.json --format sarif`

## Contract

- JSON responses include `schema_version: sdetkit.policy.v2`.
- Exit codes:
  - `0`: policy clean
  - `1`: policy regressions
  - `2`: usage/config/waiver validation error
- Waiver support with required governance fields:
  - `owner`
  - `justification`
  - `expires_on` (`YYYY-MM-DD`)
- Unknown waiver types are rejected.

## Waiver model

Use `--waivers waivers.json` with:

```json
{
  "waivers": [
    {
      "type": "security_rule_increase",
      "rule_id": "SECRET_GENERIC",
      "owner": "security-team",
      "justification": "accepted temporary migration risk",
      "expires_on": "2099-01-01"
    }
  ]
}
```

Expired or malformed waivers fail fast with deterministic machine-readable errors.
