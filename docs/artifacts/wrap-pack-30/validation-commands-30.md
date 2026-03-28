# Name 30 validation commands

```bash
python -m sdetkit name30-phase1-wrap --format json --strict
python -m sdetkit name30-phase1-wrap --emit-pack-dir docs/artifacts/name30-wrap-pack --format json --strict
python -m sdetkit name30-phase1-wrap --execute --evidence-dir docs/artifacts/name30-wrap-pack/evidence --format json --strict
python scripts/check_name30_phase1_wrap_contract.py
```
