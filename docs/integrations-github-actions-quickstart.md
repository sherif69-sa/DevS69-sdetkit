# GitHub Actions quickstart (Day 15)

A production-ready integration recipe to run `sdetkit` quality checks in GitHub Actions with quickstart, strict, and nightly variants.

## Who this recipe is for

- Maintainers who need CI guardrails in less than 5 minutes.
- Teams moving from local-only checks to PR gate automation.
- Contributors who want deterministic quality signals in pull requests.

## 5-minute setup

1. Add `.github/workflows/sdetkit-quickstart.yml` with the minimal workflow below.
2. Push a branch and open a pull request.
3. Confirm the quality-gate job passes before merge.

## Minimal workflow

```yaml
name: sdetkit-github-quickstart
on:
  pull_request:
  workflow_dispatch:

jobs:
  quality-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install -r requirements-test.txt -e .
      - run: python -m sdetkit github-actions-quickstart --format json --strict
      - run: python -m pytest -q tests/test_cli_sdetkit.py tests/test_github_actions_quickstart.py
```

## Strict workflow variant

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
      - run: python -m sdetkit github-actions-quickstart --format json --strict
      - run: python scripts/check_day15_github_actions_quickstart_contract.py
```

## Nightly reliability variant

```yaml
name: sdetkit-github-nightly
on:
  schedule:
    - cron: '0 4 * * *'
  workflow_dispatch:

jobs:
  nightly-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install -r requirements-test.txt -e .
      - run: python -m sdetkit doctor --format text
      - run: python -m sdetkit repo audit --format json
      - run: python -m sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/day15-github-pack/evidence --format json --strict
```

## Fast verification commands

Run these locally before opening PRs:

```bash
python -m sdetkit doctor --format text
python -m sdetkit repo audit --format json
python -m pytest -q tests/test_github_actions_quickstart.py tests/test_cli_help_lists_subcommands.py
python scripts/check_day15_github_actions_quickstart_contract.py
python -m sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/day15-github-pack/evidence --format json --strict
```

## Multi-channel distribution loop

1. Post merged workflow update in engineering chat with before/after CI timing.
2. Publish docs update in `docs/index.md` weekly rollout section.
3. Share one artifact (`day15-execution-summary.json`) in team retro for adoption tracking.

## Failure recovery playbook

- If checks fail from missing docs content, run `--write-defaults` and rerun strict validation.
- If tests fail, keep quickstart lane blocking and move nightly lane to diagnostics-only until stable.
- If flaky behavior appears, attach evidence logs from `--execute --evidence-dir` to the incident thread.

## Rollout checklist

- [ ] Workflow is enabled on `pull_request` and `workflow_dispatch`.
- [ ] CI installs from `requirements-test.txt` and editable package source.
- [ ] Day 15 contract check is part of docs validation.
- [ ] Execution evidence bundle is generated weekly.
- [ ] Team channel has a pinned link to this quickstart page.
