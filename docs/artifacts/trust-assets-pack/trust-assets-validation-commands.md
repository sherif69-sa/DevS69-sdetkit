# Trust assets validation commands

```bash
python -m sdetkit trust-assets --format json --strict
python -m sdetkit trust-assets --emit-pack-dir docs/artifacts/trust-assets-pack --format json --strict
python -m sdetkit trust-assets --execute --evidence-dir docs/artifacts/trust-assets-pack/evidence --format json --strict
python scripts/check_trust_assets_contract.py
```
