# Day 22 validation commands

```bash
python -m sdetkit trust-assets --format json --strict
python -m sdetkit trust-assets --emit-pack-dir docs/artifacts/day22-trust-pack --format json --strict
python -m sdetkit trust-assets --execute --evidence-dir docs/artifacts/day22-trust-pack/evidence --format json --strict
python scripts/check_day22_trust_signal_upgrade_contract.py
```
