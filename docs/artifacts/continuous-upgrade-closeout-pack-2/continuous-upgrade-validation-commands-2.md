# Cycle 2 validation commands

```bash
python -m sdetkit continuous-upgrade-closeout-2 --format json --strict
python -m sdetkit continuous-upgrade-closeout-2 --emit-pack-dir docs/artifacts/continuous-upgrade-closeout-2-pack --format json --strict
python scripts/check_continuous_upgrade_cycle2_closeout_contract.py --skip-evidence
```
