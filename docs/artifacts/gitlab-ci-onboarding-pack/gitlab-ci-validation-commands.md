# GitLab CI validation commands

```bash
python -m sdetkit doctor --format text
python -m sdetkit repo audit --format json
python -m pytest -q tests/test_gitlab_ci_quickstart.py tests/test_cli_help_lists_subcommands.py
python scripts/check_gitlab_ci_onboarding_contract.py
python -m sdetkit gitlab-ci-onboarding --variant strict --bootstrap-pipeline --pipeline-path .gitlab-ci.yml --format json --strict
python -m sdetkit gitlab-ci-onboarding --execute --evidence-dir docs/artifacts/gitlab-ci-onboarding-pack/evidence --format json --strict
```
