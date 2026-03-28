# Cycle 3 validation commands

```bash
python -m sdetkit continuous-upgrade-closeout-3 --format json --strict
python -m sdetkit continuous-upgrade-closeout-3 --emit-pack-dir docs/artifacts/continuous-upgrade-closeout-3-pack --format json --strict
python scripts/check_continuous_upgrade_cycle3_closeout_contract.py --skip-evidence
```
