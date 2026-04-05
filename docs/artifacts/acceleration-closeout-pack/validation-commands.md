# Acceleration validation commands

```bash
python -m sdetkit acceleration-closeout --format json --strict
python -m sdetkit acceleration-closeout --emit-pack-dir docs/artifacts/acceleration-closeout-pack --format json --strict
python scripts/check_acceleration_closeout_contract.py --skip-evidence
```
