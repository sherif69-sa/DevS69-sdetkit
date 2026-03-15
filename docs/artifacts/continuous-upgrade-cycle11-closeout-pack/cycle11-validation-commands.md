# Cycle 11 validation commands

```bash
python -m sdetkit continuous-upgrade-cycle11-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle11-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle11-closeout-pack --format json --strict
python scripts/check_continuous_upgrade_cycle11_closeout_contract.py --skip-evidence
```
