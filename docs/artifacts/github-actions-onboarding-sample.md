# GitHub Actions quickstart report

- Score: **100.0** (18/18)
- Page: `docs/integrations-github-actions-quickstart.md`
- Variant: `strict`

## Required sections

- `## Who this recipe is for`
- `## 5-minute setup`
- `## Minimal workflow`
- `## Strict workflow variant`
- `## Nightly reliability variant`
- `## Fast verification commands`
- `## Multi-channel distribution loop`
- `## Failure recovery playbook`
- `## Rollout checklist`

## Required commands

```bash
python -m sdetkit doctor --format text
python -m sdetkit repo audit --format json
python -m pytest -q tests/test_github_actions_quickstart.py tests/test_cli_help_lists_subcommands.py
python scripts/check_github_actions_onboarding_contract.py
python -m sdetkit github-actions-onboarding --execute --evidence-dir docs/artifacts/github-actions-onboarding-pack/evidence --format json --strict
```

## Selected workflow

```yaml
name: sdetkit-github-strict
on:
  pull_request:
  workflow_dispatch:

jobs:
  strict-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install -r requirements-test.txt -e .
      - run: python -m pytest -q tests/test_cli_sdetkit.py tests/test_github_actions_quickstart.py tests/test_cli_help_lists_subcommands.py
      - run: python -m sdetkit github-actions-onboarding --format json --strict
      - run: python scripts/check_github_actions_onboarding_contract.py
```

## Quickstart coverage gaps

- none

## Actions

- Open page: `docs/integrations-github-actions-quickstart.md`
- Validate: `sdetkit github-actions-onboarding --format json --strict`
- Validate strict variant: `sdetkit github-actions-onboarding --format json --variant strict --strict`
- Write defaults: `sdetkit github-actions-onboarding --write-defaults --format json --strict`
- Export artifact: `sdetkit github-actions-onboarding --format markdown --variant strict --output docs/artifacts/github-actions-onboarding-sample.md`
- Emit pack: `sdetkit github-actions-onboarding --emit-pack-dir docs/artifacts/github-actions-onboarding-pack --format json --strict`
- Execute: `sdetkit github-actions-onboarding --execute --evidence-dir docs/artifacts/github-actions-onboarding-pack/evidence --format json --strict`
