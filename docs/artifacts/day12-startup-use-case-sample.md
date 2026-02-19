# Day 12 startup use-case page

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

- `docs/artifacts/day12-startup-pack/startup-day12-checklist.md`
- `docs/artifacts/day12-startup-pack/startup-day12-ci.yml`
- `docs/artifacts/day12-startup-pack/startup-day12-risk-register.md`

## Missing use-case content

- none

## Actions

- `docs/use-cases-startup-small-team.md`
- `sdetkit startup-use-case --format json --strict`
- `sdetkit startup-use-case --write-defaults --format json --strict`
- `sdetkit startup-use-case --format markdown --output docs/artifacts/day12-startup-use-case-sample.md`
- `sdetkit startup-use-case --emit-pack-dir docs/artifacts/day12-startup-pack --format json --strict`
