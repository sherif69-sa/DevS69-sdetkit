# Day 86 validation commands

```bash
python -m sdetkit day86-launch-readiness-closeout --format json --strict
python -m sdetkit day86-launch-readiness-closeout --emit-pack-dir docs/artifacts/day86-launch-readiness-closeout-pack --format json --strict
python scripts/check_day86_launch_readiness_closeout_contract.py --skip-evidence
```
