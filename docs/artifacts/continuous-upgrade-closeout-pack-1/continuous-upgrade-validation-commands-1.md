# Cycle 1 validation commands

```bash
python -m sdetkit continuous-upgrade-cycle1-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle1-closeout --emit-pack-dir docs/artifacts/continuous-upgrade-cycle1-closeout-pack --format json --strict
python scripts/check_continuous_upgrade_contract_1.py --skip-evidence
```
