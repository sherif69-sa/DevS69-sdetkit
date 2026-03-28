# Cycle 10 validation commands

```bash
python -m sdetkit continuous-upgrade-cycle10-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle10-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle10-closeout-pack --format json --strict
python scripts/check_continuous_upgrade_cycle10_closeout_contract.py --skip-evidence
```
