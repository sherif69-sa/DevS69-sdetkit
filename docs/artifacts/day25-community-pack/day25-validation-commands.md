# Day 25 validation commands

```bash
python -m sdetkit community-activation --format json --strict
python -m sdetkit community-activation --emit-pack-dir docs/artifacts/day25-community-pack --format json --strict
python -m sdetkit community-activation --execute --evidence-dir docs/artifacts/day25-community-pack/evidence --format json --strict
python scripts/check_day25_community_activation_contract.py
```
