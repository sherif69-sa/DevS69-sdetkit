# Cycle 1 validation commands

```bash
python -m sdetkit continuous-upgrade-closeout-1 --format json --strict
python -m sdetkit continuous-upgrade-closeout-1 --emit-pack-dir docs/artifacts/continuous-upgrade-closeout-1-pack --format json --strict
python scripts/check_continuous_upgrade_contract_1.py --skip-evidence
```
