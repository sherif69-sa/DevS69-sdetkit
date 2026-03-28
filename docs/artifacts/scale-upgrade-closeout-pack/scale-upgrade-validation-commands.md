# Scale upgrade validation commands

```bash
python -m sdetkit scale-upgrade-closeout --format json --strict
python -m sdetkit scale-upgrade-closeout --emit-pack-dir docs/artifacts/scale-upgrade-closeout-pack --format json --strict
python scripts/check_scale_upgrade_closeout_contract.py --skip-evidence
```
