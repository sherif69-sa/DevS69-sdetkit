# Day 40 validation commands

```bash
python -m sdetkit day40-scale-lane --format json --strict
python -m sdetkit day40-scale-lane --emit-pack-dir docs/artifacts/day40-scale-lane-pack --format json --strict
python -m sdetkit day40-scale-lane --execute --evidence-dir docs/artifacts/day40-scale-lane-pack/evidence --format json --strict
python scripts/check_day40_scale_lane_contract.py
```
