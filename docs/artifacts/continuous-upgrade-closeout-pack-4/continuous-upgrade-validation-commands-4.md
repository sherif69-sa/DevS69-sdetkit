# Cycle 4 validation commands

```bash
python -m sdetkit continuous-upgrade-closeout-4 --format json --strict
python -m sdetkit continuous-upgrade-closeout-4 --emit-pack-dir docs/artifacts/continuous-upgrade-closeout-4-pack --format json --strict
python scripts/check_continuous_upgrade_cycle4_closeout_contract.py --skip-evidence
```
