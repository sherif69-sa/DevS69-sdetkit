# Cycle 15 ultra upgrade report

## Cycle 15 big upgrade

Cycle 15 now ships a **full GitHub Actions integration operating loop**:

- quickstart + strict + nightly workflow variants,
- contract-backed docs validation,
- pack generation for rollout/distribution,
- and execution evidence capture (`cycle15-execution-summary.json` + command logs).

## What changed

- Upgraded `sdetkit github-actions-quickstart` with:
  - `--variant` (`minimal`, `strict`, `nightly`)
  - `--execute` with command-run status capture
  - `--evidence-dir` + command log exports
  - enhanced strict checks for expanded Cycle 15 content
- Expanded Cycle 15 integration docs with:
  - strict and nightly workflow snippets,
  - multi-channel distribution loop,
  - failure recovery playbook.
- Expanded emitted pack artifacts with strict/nightly workflows and distribution plan.
- Strengthened tests for execute/evidence behavior and strict failure paths.
- Hardened contract check script to enforce Cycle 15 closeout assets.

## Validation commands

```bash
python -m pytest -q tests/test_github_actions_quickstart.py tests/test_cli_help_lists_subcommands.py
python -m sdetkit github-actions-quickstart --format json --strict
python -m sdetkit github-actions-quickstart --format json --variant strict --strict
python -m sdetkit github-actions-quickstart --write-defaults --format json --strict
python -m sdetkit github-actions-quickstart --emit-pack-dir docs/artifacts/cycle15-github-pack --format json --strict
python -m sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/cycle15-github-pack/evidence --format json --strict
python scripts/check_github_actions_quickstart_contract.py
```

## Artifacts

- `docs/integrations-github-actions-quickstart.md`
- `docs/artifacts/cycle15-github-actions-quickstart-sample.md`
- `docs/artifacts/cycle15-github-pack/cycle15-github-checklist.md`
- `docs/artifacts/cycle15-github-pack/cycle15-sdetkit-quickstart.yml`
- `docs/artifacts/cycle15-github-pack/cycle15-sdetkit-strict.yml`
- `docs/artifacts/cycle15-github-pack/cycle15-sdetkit-nightly.yml`
- `docs/artifacts/cycle15-github-pack/cycle15-distribution-plan.md`
- `docs/artifacts/cycle15-github-pack/cycle15-validation-commands.md`
- `docs/artifacts/cycle15-github-pack/evidence/cycle15-execution-summary.json`
