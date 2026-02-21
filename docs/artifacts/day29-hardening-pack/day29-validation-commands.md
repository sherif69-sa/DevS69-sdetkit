# Day 29 validation commands

```bash
python -m sdetkit day29-phase1-hardening --format json --strict
python -m sdetkit day29-phase1-hardening --emit-pack-dir docs/artifacts/day29-hardening-pack --format json --strict
python -m sdetkit day29-phase1-hardening --execute --evidence-dir docs/artifacts/day29-hardening-pack/evidence --format json --strict
python scripts/check_day29_phase1_hardening_contract.py
```
