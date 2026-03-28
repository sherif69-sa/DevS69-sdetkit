# Cycle 5 validation commands

```bash
python -m sdetkit continuous-upgrade-cycle5-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle5-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle5-closeout-pack --format json --strict
python scripts/check_continuous_upgrade_cycle5_closeout_contract.py --skip-evidence
```
