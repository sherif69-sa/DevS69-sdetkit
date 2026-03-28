# Day 37 validation commands

```bash
python -m sdetkit experiment-lane --format json --strict
python -m sdetkit experiment-lane --emit-pack-dir docs/artifacts/experiment-lane-pack --format json --strict
python -m sdetkit experiment-lane --execute --evidence-dir docs/artifacts/experiment-lane-pack/evidence --format json --strict
python scripts/check_experiment_lane_contract.py
```
