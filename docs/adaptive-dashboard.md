# Adaptive next-wave dashboard

The adaptive next-wave dashboard is a deterministic, local-only HTML artifact that links the adaptive evidence set for release-room review. It does not host data, phone home, or execute remediation; it only summarizes and links artifacts already produced by other adaptive commands.

## Command

```bash
python -m sdetkit adaptive dashboard \
  --diagnosis build/sdetkit/adaptive-diagnosis.json \
  --brief build/sdetkit/operator-brief.md \
  --portfolio build/sdetkit/adaptive-portfolio.json \
  --fix-audit build/sdetkit/fix-audit-summary.json \
  --governance build/sdetkit/enterprise-governance.json \
  --adapter build/sdetkit/integration-adapter.json \
  --analytics build/sdetkit/adaptive-enterprise-analytics.json \
  --remediation-policy build/sdetkit/remediation-policy-result.json \
  --out build/sdetkit/adaptive-dashboard.html
```

Use JSON output for automation checks:

```bash
python -m sdetkit adaptive dashboard \
  --analytics build/sdetkit/adaptive-enterprise-analytics.json \
  --format json \
  --out build/sdetkit/adaptive-dashboard.json
```

## Linked artifact cards

| Card | Typical source |
| --- | --- |
| Adaptive diagnosis | `sdetkit adaptive diagnosis` output or saved diagnosis JSON |
| Operator brief | `sdetkit adaptive brief` Markdown/JSON/comment output |
| Portfolio rollup | `sdetkit adaptive portfolio-rollup --format json` |
| Fix audit | `sdetkit adaptive fix-audit summarize --format json` or JSONL audit records |
| Enterprise governance | `sdetkit adaptive enterprise-governance report --format json` |
| Integration adapter | `sdetkit adaptive integration-adapter validate --format json` |
| Enterprise analytics | `sdetkit adaptive enterprise-analytics --format json` |
| Remediation policy | `sdetkit adaptive remediation-policy validate --format json` |

Missing optional artifacts are rendered as warning cards so the dashboard remains usable during partial rollout.

## Guardrails

- Local-only static HTML output.
- Deterministic card ordering.
- No external assets, scripts, tracking, or hosted dependencies.
- Links point to local artifacts supplied on the command line.
- Unknown or review-required diagnoses remain governed by the remediation policy and patch-plan lanes; the dashboard only displays their evidence.
