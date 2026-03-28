# Cycle 7 validation commands

```bash
python -m sdetkit continuous-upgrade-closeout-7 --format json --strict
python -m sdetkit continuous-upgrade-closeout-7 --emit-pack-dir docs/artifacts/continuous-upgrade-closeout-7-pack --format json --strict
python scripts/check_continuous_upgrade_cycle7_closeout_contract.py --skip-evidence
```
