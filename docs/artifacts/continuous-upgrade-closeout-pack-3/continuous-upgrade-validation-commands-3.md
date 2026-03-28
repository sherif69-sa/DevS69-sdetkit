# Cycle 3 validation commands

```bash
python -m sdetkit continuous-upgrade-cycle3-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle3-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle3-closeout-pack --format json --strict
python scripts/check_continuous_upgrade_cycle3_closeout_contract.py --skip-evidence
```
