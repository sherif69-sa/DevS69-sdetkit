# Cycle 30 validation commands

```bash
python -m sdetkit phase1-wrap --format json --strict
python -m sdetkit phase1-wrap --emit-pack-dir docs/artifacts/phase1-wrap-pack --format json --strict
python -m sdetkit phase1-wrap --execute --evidence-dir docs/artifacts/phase1-wrap-pack/evidence --format json --strict
python scripts/check_phase1_wrap_contract.py
```
