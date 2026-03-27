# GitLab CI quickstart report

- Score: **100.0** (19/19)
- Page: `docs/integrations-gitlab-ci-quickstart.md`
- Variant: `strict`

## Required sections

- `## Who this recipe is for`
- `## 5-minute setup`
- `## Minimal pipeline`
- `## Strict pipeline variant`
- `## Nightly reliability variant`
- `## Fast verification commands`
- `## Multi-channel distribution loop`
- `## Failure recovery playbook`
- `## Rollout checklist`

## Required commands

```bash
python -m sdetkit doctor --format text
python -m sdetkit repo audit --format json
python -m pytest -q tests/test_gitlab_ci_quickstart.py tests/test_cli_help_lists_subcommands.py
python scripts/check_gitlab_ci_onboarding_contract.py
python -m sdetkit gitlab-ci-onboarding --variant strict --bootstrap-pipeline --pipeline-path .gitlab-ci.yml --format json --strict
python -m sdetkit gitlab-ci-onboarding --execute --evidence-dir docs/artifacts/gitlab-ci-onboarding-pack/evidence --format json --strict
```

## Selected pipeline

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
    - python -m sdetkit gitlab-ci-onboarding --format json --strict
    - python scripts/check_gitlab_ci_onboarding_contract.py
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_PIPELINE_SOURCE == "web"
```

## Quickstart coverage gaps

- none

## Actions

- Open page: `docs/integrations-gitlab-ci-quickstart.md`
- Validate: `sdetkit gitlab-ci-onboarding --format json --strict`
- Validate strict variant: `sdetkit gitlab-ci-onboarding --format json --variant strict --strict`
- Write defaults: `sdetkit gitlab-ci-onboarding --write-defaults --format json --strict`
- Export artifact: `sdetkit gitlab-ci-onboarding --format markdown --variant strict --output docs/artifacts/gitlab-ci-onboarding-sample.md`
- Emit pack: `sdetkit gitlab-ci-onboarding --emit-pack-dir docs/artifacts/gitlab-ci-onboarding-pack --format json --strict`
- Bootstrap pipeline: `sdetkit gitlab-ci-onboarding --variant strict --bootstrap-pipeline --pipeline-path .gitlab-ci.yml --format json --strict`
- Execute: `sdetkit gitlab-ci-onboarding --execute --evidence-dir docs/artifacts/gitlab-ci-onboarding-pack/evidence --format json --strict`
