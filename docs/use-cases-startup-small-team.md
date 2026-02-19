# Startup + small-team workflow

A practical landing page for lean engineering teams that need reliable quality gates without heavy process overhead.

## Who this is for

- Teams with 2-20 engineers shipping quickly.
- Founders or EMs who need confidence before each release.
- QA/SDET owners establishing a repeatable baseline in one sprint.

## 10-minute startup path

Use this sequence to move from clone to reliable checks quickly:

```bash
python -m sdetkit doctor --format text
python -m sdetkit repo audit --json
python -m sdetkit security --strict
python -m pytest -q tests/test_startup_use_case.py tests/test_cli_help_lists_subcommands.py
python -m sdetkit report --out reports/startup-weekly.json
```

## Weekly operating rhythm

1. Run `doctor` and `repo audit` at sprint start to catch drift early.
2. Run `security --strict` before release candidate tagging.
3. Publish `report` artifacts to preserve a quality trail.

## Guardrails that prevent regressions

- **Deterministic checks:** lock expected commands in CI and pre-merge workflows.
- **Single source of evidence:** save generated report artifacts under `reports/`.
- **Fast rollback:** revert to last known-good baseline when score drops.

## CI fast-lane recipe

Use this minimal workflow to enforce the Day 12 page contract in PRs:

```yaml
name: startup-quality-fast-lane
on:
  pull_request:
  workflow_dispatch:

jobs:
  startup-fast-lane:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install -r requirements-test.txt -e .
      - run: python -m sdetkit startup-use-case --format json --strict
      - run: python scripts/check_day12_startup_use_case_contract.py
```

## KPI snapshot for lean teams

Track these signals every week:

- Mean time from PR open to merge.
- Failed quality gates per sprint.
- Security findings closed within SLA.
- New contributor first-PR success rate.

## Exit criteria to graduate to enterprise workflow

Move to the enterprise/regulated path once you need:

- Separation of duties and approval workflows.
- Extended audit retention and compliance mapping.
- Multi-repository governance at org level.
