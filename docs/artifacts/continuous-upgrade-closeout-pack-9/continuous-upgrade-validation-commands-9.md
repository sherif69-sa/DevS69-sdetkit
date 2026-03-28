# Cycle 9 validation commands

```bash
python -m sdetkit continuous-upgrade-cycle9-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle9-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle9-closeout-pack --format json --strict
python scripts/check_continuous_upgrade_cycle9_closeout_contract.py --skip-evidence
```
