# Cycle 8 validation commands

```bash
python -m sdetkit continuous-upgrade-cycle8-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle8-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle8-closeout-pack --format json --strict
python scripts/check_continuous_upgrade_cycle8_closeout_contract.py --skip-evidence
```
