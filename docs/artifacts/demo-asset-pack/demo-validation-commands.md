# Cycle 33 validation commands

```bash
python -m sdetkit demo-asset --format json --strict
python -m sdetkit demo-asset --emit-pack-dir docs/artifacts/demo-asset-pack --format json --strict
python -m sdetkit demo-asset --execute --evidence-dir docs/artifacts/demo-asset-pack/evidence --format json --strict
python scripts/check_demo_asset_contract.py
```
