# External contribution report

## What shipped

- Added `external-contribution` to enforce starter-task spotlight, discoverability, and response-SLA readiness.
- Added strict docs-contract checks for external-contribution guidance.
- Added a deterministic external-contribution pack and execution-evidence mode.
- Added dedicated contract validation script and tests.

## Key command paths

```bash
python -m sdetkit external-contribution --format json --strict
python -m sdetkit external-contribution --emit-pack-dir docs/artifacts/external-contribution-pack --format json --strict
python -m sdetkit external-contribution --execute --evidence-dir docs/artifacts/external-contribution-pack/evidence --format json --strict
python scripts/check_external_contribution_contract.py
```

## Closeout criteria

- External-contribution score >= 90 with no critical failures.
- Integration page includes all required sections + command contract.
- README/docs index discoverability links in place.
- Evidence bundle generated and review-ready.
