# Cycle 36 validation commands

```bash
python -m sdetkit distribution-closeout --format json --strict
python -m sdetkit distribution-closeout --emit-pack-dir docs/artifacts/distribution-closeout-pack --format json --strict
python -m sdetkit distribution-closeout --execute --evidence-dir docs/artifacts/distribution-closeout-pack/evidence --format json --strict
python scripts/check_distribution_closeout_contract.py
```
