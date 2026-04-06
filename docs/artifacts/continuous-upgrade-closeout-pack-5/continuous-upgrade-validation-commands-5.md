# Cycle 5 validation commands

```bash
python -m sdetkit continuous-upgrade-closeout-5 --format json --strict
python -m sdetkit continuous-upgrade-closeout-5 --emit-pack-dir docs/artifacts/continuous-upgrade-closeout-5-pack --format json --strict
python scripts/check_continuous_upgrade_closeout_contract.py --skip-evidence
```
