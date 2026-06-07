#  validation commands

```bash
python -m sdetkit trust-assets-refresh-completion --format json --strict
python -m sdetkit trust-assets-refresh-completion --emit-pack-dir docs/artifacts/trust-assets-refresh-completion-pack --format json --strict
python scripts/check_trust_assets_refresh_completion_contract.py --skip-evidence
```
