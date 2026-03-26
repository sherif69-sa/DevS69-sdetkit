# Cycle 6 validation commands

```bash
python -m sdetkit continuous-upgrade-cycle6-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle6-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle6-closeout-pack --format json --strict
python scripts/check_continuous_upgrade_cycle6_closeout_contract.py --skip-evidence
```
