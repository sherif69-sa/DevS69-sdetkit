# Adaptive integration adapters

Adaptive integration adapters define the minimum artifact contract for publishing adaptive evidence from CI providers.

Supported providers:

- `github-actions`
- `gitlab`
- `jenkins`
- `local`

## Required artifacts

| Artifact key | Purpose |
| --- | --- |
| `adaptive_diagnosis_json` | Machine-readable adaptive diagnosis output. |
| `operator_brief_md` | Human-readable release/operator handoff. |

Optional artifacts include `fix_audit_jsonl`, `portfolio_rollup_json`, and `enterprise_governance_json`.

## Validate an adapter payload

Create an artifact map:

```json
{
  "artifacts": {
    "adaptive_diagnosis_json": "build/sdetkit/adaptive-diagnosis.json",
    "operator_brief_md": "build/sdetkit/operator-brief.md",
    "fix_audit_jsonl": ".sdetkit/adaptive-fix-audit.jsonl"
  }
}
```

Then validate it for the target provider:

```bash
python -m sdetkit adaptive integration-adapter validate \
  --provider github-actions \
  --artifacts build/sdetkit/adaptive-artifacts.json \
  --root . \
  --format json \
  --out build/sdetkit/adaptive-adapter-contract.json
```

The contract returns `READY` only when required artifacts exist. Otherwise it returns `BLOCKED` with the missing input keys so the CI job can fail before publishing incomplete evidence.

## Provider behavior

| Provider | Upload target |
| --- | --- |
| `github-actions` | `actions-artifact` |
| `gitlab` | `job-artifacts` |
| `jenkins` | `archiveArtifacts` |
| `local` | `filesystem` |

The adapter contract is intentionally provider-light: it normalizes required artifact paths and target names, while each CI template remains responsible for native upload syntax.
