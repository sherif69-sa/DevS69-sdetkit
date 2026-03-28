# Day 25 validation commands

```bash
python -m sdetkit community-activation --format json --strict
python -m sdetkit community-activation --emit-pack-dir docs/artifacts/community-activation-pack --format json --strict
python -m sdetkit community-activation --execute --evidence-dir docs/artifacts/community-activation-pack/evidence --format json --strict
python scripts/check_community_activation_contract.py
```
