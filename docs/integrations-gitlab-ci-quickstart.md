# GitLab CI quickstart (Day 16)

A production-ready integration recipe to run `sdetkit` quality checks in GitLab CI with quickstart, strict, and nightly variants.

## Who this recipe is for

- Maintainers who need CI guardrails in less than 5 minutes.
- Teams migrating from ad-hoc local checks into merge request quality gates.
- Contributors who want deterministic quality signals in merge request pipelines.

## 5-minute setup

1. Add `.gitlab-ci.yml` using the minimal pipeline below.
2. Open a merge request to trigger the quality gate.
3. Confirm the quickstart-gate job passes before merge.

## Minimal pipeline

```yaml
stages:
  - quality

variables:
  PIP_DISABLE_PIP_VERSION_CHECK: "1"

quickstart-gate:
  stage: quality
  image: python:3.11
  script:
    - python -m pip install -r requirements-test.txt -e .
    - python -m sdetkit gitlab-ci-quickstart --format json --strict
    - python -m pytest -q tests/test_cli_sdetkit.py tests/test_gitlab_ci_quickstart.py
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_PIPELINE_SOURCE == "web"
```

## Strict pipeline variant

```yaml
stages:
  - quality

variables:
  PIP_DISABLE_PIP_VERSION_CHECK: "1"

strict-gate:
  stage: quality
  image: python:3.11
  script:
    - python -m pip install -r requirements-test.txt -e .
    - python -m pytest -q tests/test_cli_sdetkit.py tests/test_gitlab_ci_quickstart.py tests/test_cli_help_lists_subcommands.py
    - python -m sdetkit gitlab-ci-quickstart --format json --strict
    - python scripts/check_day16_gitlab_ci_quickstart_contract.py
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_PIPELINE_SOURCE == "web"
```

## Nightly reliability variant

```yaml
stages:
  - nightly

variables:
  PIP_DISABLE_PIP_VERSION_CHECK: "1"

nightly-audit:
  stage: nightly
  image: python:3.11
  script:
    - python -m pip install -r requirements-test.txt -e .
    - python -m sdetkit doctor --format text
    - python -m sdetkit repo audit --format json
    - python -m sdetkit gitlab-ci-quickstart --execute --evidence-dir docs/artifacts/day16-gitlab-pack/evidence --format json --strict
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - if: $CI_PIPELINE_SOURCE == "web"
```

## Fast verification commands

Run these locally before opening merge requests:

```bash
python -m sdetkit doctor --format text
python -m sdetkit repo audit --format json
python -m pytest -q tests/test_gitlab_ci_quickstart.py tests/test_cli_help_lists_subcommands.py
python scripts/check_day16_gitlab_ci_quickstart_contract.py
python -m sdetkit gitlab-ci-quickstart --variant strict --bootstrap-pipeline --pipeline-path .gitlab-ci.yml --format json --strict
python -m sdetkit gitlab-ci-quickstart --execute --evidence-dir docs/artifacts/day16-gitlab-pack/evidence --format json --strict
```

## Multi-channel distribution loop

1. Share merged `.gitlab-ci.yml` updates in engineering chat with before/after timing.
2. Publish docs updates in `docs/index.md` weekly rollout section.
3. Attach one artifact (`day16-execution-summary.json`) in retro for adoption tracking.

## Failure recovery playbook

- If checks fail because docs content drifted, run `--write-defaults` then rerun strict mode.
- If tests fail, keep strict gate required and move nightly lane to diagnostics-only until stable.
- If flaky behavior appears, attach evidence logs from `--execute --evidence-dir` to incident notes.

## Rollout checklist

- [ ] Pipeline runs for merge requests and manual dispatches.
- [ ] CI installs from `requirements-test.txt` and editable package source.
- [ ] Day 16 contract check is part of docs validation.
- [ ] Execution evidence bundle is generated weekly.
- [ ] Team channel has a pinned link to this quickstart page.
