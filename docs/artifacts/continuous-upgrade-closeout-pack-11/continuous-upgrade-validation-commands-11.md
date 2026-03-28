# Cycle 11 validation commands

```bash
python -m sdetkit continuous-upgrade-closeout-11 --format json --strict
python -m sdetkit continuous-upgrade-closeout-11 --emit-pack-dir docs/artifacts/continuous-upgrade-closeout-11-pack --format json --strict
python scripts/check_continuous_upgrade_cycle11_closeout_contract.py --skip-evidence
```
