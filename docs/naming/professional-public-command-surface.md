# Professional public command surface

This page records the maintained public command names after the professional naming sweep.

Operators should see production workflow aliases first. Deeper implementation targets and legacy phase names may remain available for compatibility, but they are not the public documentation surface.

## Maintained public Makefile surfaces

| Domain | Primary public command |
| --- | --- |
| Baseline | `make operations-baseline` |
| Baseline | `make operations-status` |
| Baseline | `make operations-next-action` |
| Baseline | `make operations-complete` |
| Release readiness | `make release-readiness-start` |
| Release readiness | `make release-readiness-workflow` |
| Release readiness | `make release-readiness-status` |
| Release readiness | `make release-readiness-start-contract` |
| Release readiness | `make release-readiness-seed` |
| Release readiness | `make release-readiness-complete` |
| Release readiness | `make release-readiness-progress` |
| Release readiness | `make release-readiness-surface-clarity` |
| Quality | `make quality-contract-check` |
| Quality | `make quality-contract-report` |
| Quality | `make quality-contract-run` |
| Governance | `make governance-contract-check` |
| Ecosystem | `make ecosystem-contract-check` |
| Metrics | `make metrics-contract-check` |

## Naming policy

Professional public names should use capability language:

- `operations-*` for operator-facing workflow entrypoints.
- `release-readiness-*` for release preparation.
- `quality-contract-*` for quality contract checks and reports.
- `governance-contract-*` for governance contract checks.
- `ecosystem-contract-*` for ecosystem readiness.
- `metrics-contract-*` for scale and metrics readiness.

Compatibility names remain available when removing them would break existing users or historical automation.

## Do not rewrite these in sweep PRs

The following surfaces are intentionally excluded from broad rename sweeps:

- historical reports
- committed generated evidence
- schema version identifiers
- generated build output
- implementation-only Makefile targets

## Verification commands

Use these checks for public naming PRs:

```bash
python scripts/check_operator_essentials_contract.py --format json
python scripts/check_operational_readiness_governance_contract.py --format json
python -m pytest -q tests/test_production_workflow_naming_aliases.py -o addopts=
python -m pytest -q tests/test_makefile_professional_contract_aliases.py -o addopts=
make proof-after-format
```

## Review checklist

- Primary docs show public production aliases first.
- Compatibility aliases still work.
- Compatibility tests prove old implementation targets remain available.
- No generated artifacts are rewritten for line count.
- No schema IDs are changed without an explicit migration contract.
