# Day 46 Validation Commands

```bash
python -m sdetkit optimization-closeout --format json --strict
python -m sdetkit optimization-closeout --emit-pack-dir docs/artifacts/optimization-closeout-pack --format json --strict
python scripts/check_optimization_closeout_contract.py --skip-evidence
```
