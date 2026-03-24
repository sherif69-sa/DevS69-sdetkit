# Name 12 startup use-case page

- Score: **100.0** (14/14)
- Page: `docs/use-cases-startup-small-team.md`

## Required sections

- `## Who this is for`
- `## 10-minute startup path`
- `## Weekly operating rhythm`
- `## Guardrails that prevent regressions`
- `## CI fast-lane recipe`
- `## KPI snapshot for lean teams`
- `## Exit criteria to graduate to enterprise workflow`

## Required commands

```bash
python -m sdetkit doctor --format text
python -m sdetkit repo audit --json
python -m sdetkit security --strict
python -m pytest -q tests/test_startup_use_case.py tests/test_cli_help_lists_subcommands.py
python -m sdetkit report --out reports/startup-weekly.json
```

## Emitted pack files

- `docs/artifacts/startup-readiness-pack/startup-readiness-checklist.md`
- `docs/artifacts/startup-readiness-pack/startup-readiness-ci.yml`
- `docs/artifacts/startup-readiness-pack/startup-readiness-risk-register.md`

## Missing use-case content

- none

## Actions

- `docs/use-cases-startup-small-team.md`
- `sdetkit startup-readiness --format json --strict`
- `sdetkit startup-readiness --write-defaults --format json --strict`
- `sdetkit startup-readiness --format markdown --output docs/artifacts/startup-readiness-sample.md`
- `sdetkit startup-readiness --emit-pack-dir docs/artifacts/startup-readiness-pack --format json --strict`
