# Cycle 9 validation commands

```bash
python -m sdetkit continuous-upgrade-closeout-9 --format json --strict
python -m sdetkit continuous-upgrade-closeout-9 --emit-pack-dir docs/artifacts/continuous-upgrade-closeout-9-pack --format json --strict
python scripts/check_continuous_upgrade_cycle9_closeout_contract.py --skip-evidence
```
