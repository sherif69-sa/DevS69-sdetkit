# Day 22 validation commands

```bash
python -m sdetkit trust-signal-upgrade --format json --strict
python -m sdetkit trust-signal-upgrade --emit-pack-dir docs/artifacts/day22-trust-pack --format json --strict
python -m sdetkit trust-signal-upgrade --execute --evidence-dir docs/artifacts/day22-trust-pack/evidence --format json --strict
python scripts/check_day22_trust_signal_upgrade_contract.py
```
