# Day 86 validation commands

```bash
python -m sdetkit launch-readiness-closeout --format json --strict
python -m sdetkit launch-readiness-closeout --emit-pack-dir docs/artifacts/launch-readiness-closeout-pack --format json --strict
python scripts/check_launch_readiness_closeout_contract.py --skip-evidence
```
