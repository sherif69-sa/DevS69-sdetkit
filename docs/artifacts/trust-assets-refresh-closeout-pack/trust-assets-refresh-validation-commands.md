# Cycle 75 validation commands

```bash
python -m sdetkit trust-assets-refresh-closeout --format json --strict
python -m sdetkit trust-assets-refresh-closeout --emit-pack-dir docs/artifacts/trust-assets-refresh-closeout-pack --format json --strict
python scripts/check_trust_assets_refresh_closeout_contract.py --skip-evidence
```
