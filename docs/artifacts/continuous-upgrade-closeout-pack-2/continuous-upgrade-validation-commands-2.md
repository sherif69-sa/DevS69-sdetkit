# Cycle 2 validation commands

```bash
python -m sdetkit continuous-upgrade-cycle2-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle2-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle2-closeout-pack --format json --strict
python scripts/check_continuous_upgrade_cycle2_closeout_contract.py --skip-evidence
```
