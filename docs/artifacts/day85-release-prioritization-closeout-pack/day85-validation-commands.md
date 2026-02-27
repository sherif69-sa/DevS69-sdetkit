# Day 85 validation commands

```bash
python -m sdetkit day85-release-prioritization-closeout --format json --strict
python -m sdetkit day85-release-prioritization-closeout --emit-pack-dir docs/artifacts/day85-release-prioritization-closeout-pack --format json --strict
python scripts/check_day85_release_prioritization_closeout_contract.py --skip-evidence
```
