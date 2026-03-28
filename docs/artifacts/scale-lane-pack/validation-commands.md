# Cycle 40 validation commands

```bash
python -m sdetkit scale-lane --format json --strict
python -m sdetkit scale-lane --emit-pack-dir docs/artifacts/scale-lane-pack --format json --strict
python -m sdetkit scale-lane --execute --evidence-dir docs/artifacts/scale-lane-pack/evidence --format json --strict
python scripts/check_scale_lane_contract.py
```
