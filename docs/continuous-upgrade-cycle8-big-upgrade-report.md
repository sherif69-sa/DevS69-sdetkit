# Cycle 8 big upgrade report

## What shipped

- Added `continuous-upgrade-cycle8-closeout` command to score Cycle 8 readiness from Cycle 7 continuous-upgrade artifacts.
- Added deterministic pack emission and execution evidence generation for impact-8 continuous-upgrade proof.
- Added strict contract validation script and tests that enforce Cycle 8 closeout quality gates.

## Command lane

```bash
python -m sdetkit continuous-upgrade-cycle8-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle8-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle8-closeout-pack --format json --strict
python -m sdetkit continuous-upgrade-cycle8-closeout --execute --evidence-dir docs/artifacts/continuous-upgrade-cycle8-closeout-pack/evidence --format json --strict
python scripts/check_continuous_upgrade_cycle8_closeout_contract.py
```
