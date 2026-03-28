# GitHub Actions validation commands

```bash
python -m sdetkit doctor --format text
python -m sdetkit repo audit --format json
python -m pytest -q tests/test_github_actions_quickstart.py tests/test_cli_help_lists_subcommands.py
python scripts/check_github_actions_onboarding_contract.py
python -m sdetkit github-actions-onboarding --execute --evidence-dir docs/artifacts/github-actions-onboarding-pack/evidence --format json --strict
```
