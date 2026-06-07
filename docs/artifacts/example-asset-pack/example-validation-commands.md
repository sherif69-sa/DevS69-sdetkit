#  validation commands

```bash
python -m sdetkit example-asset --format json --strict
python -m sdetkit example-asset --emit-pack-dir docs/artifacts/example-asset-pack --format json --strict
python -m sdetkit example-asset --execute --evidence-dir docs/artifacts/example-asset-pack/evidence --format json --strict
python scripts/check_example_asset_contract.py
```
