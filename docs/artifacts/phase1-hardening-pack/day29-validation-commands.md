# Day 29 validation commands

```bash
python -m sdetkit phase1-hardening --format json --strict
python -m sdetkit phase1-hardening --emit-pack-dir docs/artifacts/phase1-hardening-pack --format json --strict
python -m sdetkit phase1-hardening --execute --evidence-dir docs/artifacts/phase1-hardening-pack/evidence --format json --strict
python scripts/check_phase1_hardening_contract.py
```
