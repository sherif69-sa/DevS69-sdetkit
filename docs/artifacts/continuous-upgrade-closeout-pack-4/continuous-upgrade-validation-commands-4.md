# Cycle 4 validation commands

```bash
python -m sdetkit continuous-upgrade-cycle4-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle4-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle4-closeout-pack --format json --strict
python scripts/check_continuous_upgrade_cycle4_closeout_contract.py --skip-evidence
```
