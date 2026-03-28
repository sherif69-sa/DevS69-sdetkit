# Cycle 7 validation commands

```bash
python -m sdetkit continuous-upgrade-cycle7-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle7-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle7-closeout-pack --format json --strict
python scripts/check_continuous_upgrade_cycle7_closeout_contract.py --skip-evidence
```
