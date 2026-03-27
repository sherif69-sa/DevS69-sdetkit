# Trust assets report

## Trust assets report

Trust assets provides a deterministic **trust visibility lane** so maintainers can prove security and policy visibility before promotion, with weighted scoring and critical-failure gates.

## What shipped

- Upgraded `sdetkit trust-assets` to a weighted trust matrix: badge visibility, policy-doc/link discoverability, and workflow/docs-index governance checks.
- Added trust-assets integration docs and contract checks for required sections, commands, and generated artifacts.
- Expanded the trust-assets pack outputs with action-plan guidance in addition to summary, scorecard, checklist, validation commands, and execution evidence.
- Added README/docs index/CLI references and tests for command dispatch/help coverage.

## Validation commands

```bash
python -m pytest -q tests/test_trust_assets.py tests/test_cli_help_lists_subcommands.py
python -m sdetkit trust-assets --format json --strict
python -m sdetkit trust-assets --format markdown --output docs/artifacts/trust-assets-sample.md
python -m sdetkit trust-assets --emit-pack-dir docs/artifacts/trust-assets-pack --format json --strict
python -m sdetkit trust-assets --execute --evidence-dir docs/artifacts/trust-assets-pack/evidence --format json --strict
python scripts/check_trust_assets_contract.py
```

## Closeout

Trust assets now provides a trust visibility control point that can be run before releases to keep reliability and governance posture obvious to new adopters.
