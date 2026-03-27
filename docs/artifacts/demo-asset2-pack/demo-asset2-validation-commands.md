# Day 34 validation commands

```bash
python -m sdetkit demo-asset2 --format json --strict
python -m sdetkit demo-asset2 --emit-pack-dir docs/artifacts/demo-asset2-pack --format json --strict
python -m sdetkit demo-asset2 --execute --evidence-dir docs/artifacts/demo-asset2-pack/evidence --format json --strict
python scripts/check_demo_asset2_contract.py
```
