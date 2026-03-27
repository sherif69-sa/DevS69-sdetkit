# Day 44 Validation Commands

```bash
python -m sdetkit scale-closeout --format json --strict
python -m sdetkit scale-closeout --emit-pack-dir docs/artifacts/scale-closeout-pack --format json --strict
python scripts/check_day44_scale_closeout_contract.py --skip-evidence
```
