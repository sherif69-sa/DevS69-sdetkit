# Cycle 8 big upgrade report

## What shipped

- Added `continuous-upgrade-completion-8` command to score Cycle 8 readiness from Cycle 7 continuous-upgrade artifacts.
- Added deterministic pack emission and execution evidence generation for impact-8 continuous-upgrade proof.
- Added strict contract validation script and tests that enforce Cycle 8 completion report quality gates.

## Command lane

```bash
python -m sdetkit continuous-upgrade-completion-8 --format json --strict
python -m sdetkit continuous-upgrade-completion-8 --emit-pack-dir docs/artifacts/continuous-upgrade-completion-8-pack --format json --strict
python -m sdetkit continuous-upgrade-completion-8 --execute --evidence-dir docs/artifacts/continuous-upgrade-completion-8-pack/evidence --format json --strict
python scripts/check_continuous_upgrade_completion_contract.py
```
