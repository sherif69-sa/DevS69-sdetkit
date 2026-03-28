# Cycle 10 validation commands

```bash
python -m sdetkit continuous-upgrade-closeout-10 --format json --strict
python -m sdetkit continuous-upgrade-closeout-10 --emit-pack-dir docs/artifacts/continuous-upgrade-closeout-10-pack --format json --strict
python scripts/check_continuous_upgrade_cycle10_closeout_contract.py --skip-evidence
```
