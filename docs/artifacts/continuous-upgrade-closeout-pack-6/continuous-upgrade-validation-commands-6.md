# Cycle 6 validation commands

```bash
python -m sdetkit continuous-upgrade-closeout-6 --format json --strict
python -m sdetkit continuous-upgrade-closeout-6 --emit-pack-dir docs/artifacts/continuous-upgrade-closeout-6-pack --format json --strict
python scripts/check_continuous_upgrade_closeout_contract.py --skip-evidence
```
