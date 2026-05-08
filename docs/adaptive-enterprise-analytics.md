# Adaptive enterprise analytics

Adaptive enterprise analytics turns local adaptive portfolio and fix-audit artifacts into a leadership-ready release signal. It stays evidence-first: every metric is derived from a portfolio rollup JSON file and a fix-audit JSONL file produced by the existing adaptive commands.

## Command

```bash
python -m sdetkit adaptive enterprise-analytics \
  --portfolio build/sdetkit/adaptive-portfolio.json \
  --fix-audit .sdetkit/adaptive-fix-audit.jsonl \
  --format json \
  --out build/sdetkit/adaptive-enterprise-analytics.json
```

The module can also be run directly:

```bash
python -m sdetkit.adaptive_enterprise_analytics \
  --portfolio build/sdetkit/adaptive-portfolio.json \
  --fix-audit .sdetkit/adaptive-fix-audit.jsonl \
  --format text
```

## Metrics emitted

| Metric | Meaning |
| --- | --- |
| `remediation_success_rate` | Share of planned/applied remediation decisions that reached a matching `proof_passed` record. |
| `missing_proof_rate` | Share of planned/applied remediation decisions that do not yet have proof, revert, or rejection closure. |
| `failed_proof_rate` | Share of proof outcomes that are `proof_failed`. |
| `mean_time_to_proof_seconds` | Average elapsed time from planned/applied remediation to the earliest matching proof outcome when timestamps are available. |
| `top_recurring_source_codes` | Combined recurring source codes from portfolio scenarios and fix-audit records. |
| `top_risky_repos` | Portfolio repositories ordered by risk score when recurrence-by-repo evidence is present. |

## Release-room recommendation

The analytics recommendation is intentionally conservative:

- `NO_SHIP` when failed proof exists or the portfolio recommendation is `NO_SHIP`.
- `SHIP_WITH_CONTROLS` when proof is missing or the portfolio requires controls.
- `SHIP` only when portfolio and proof evidence are complete.

Unknown or review-required diagnoses remain review-first; this lane reports risk and proof completeness but does not enable automatic remediation.
