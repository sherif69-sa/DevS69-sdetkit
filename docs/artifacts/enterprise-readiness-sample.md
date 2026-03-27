# Enterprise readiness report

- Score: **100.0** (15/15)
- Page: `docs/use-cases-enterprise-regulated.md`

## Required sections

- `## Who this is for`
- `## 15-minute enterprise baseline`
- `## Governance operating cadence`
- `## Compliance evidence controls`
- `## CI compliance lane recipe`
- `## KPI and control dashboard`
- `## Automated evidence bundle`
- `## Rollout model across business units`

## Required commands

```bash
python -m sdetkit repo audit . --profile enterprise --format json
python -m sdetkit security report --format text
python -m sdetkit policy snapshot --output .sdetkit/enterprise-readiness-policy-snapshot.json
python -m pytest -q tests/test_enterprise_readiness.py tests/test_cli_help_lists_subcommands.py
python scripts/check_enterprise_readiness_contract.py
```

## Use-case coverage gaps

- none

## Actions

- Open page: `docs/use-cases-enterprise-regulated.md`
- Validate: `sdetkit enterprise-readiness --format json --strict`
- Write defaults: `sdetkit enterprise-readiness --write-defaults --format json --strict`
- Export artifact: `sdetkit enterprise-readiness --format markdown --output docs/artifacts/enterprise-readiness-sample.md`
- Emit pack: `sdetkit enterprise-readiness --emit-pack-dir docs/artifacts/enterprise-readiness-pack --format json --strict`
- Execute: `sdetkit enterprise-readiness --execute --evidence-dir docs/artifacts/enterprise-readiness-pack/evidence --format json --strict`
