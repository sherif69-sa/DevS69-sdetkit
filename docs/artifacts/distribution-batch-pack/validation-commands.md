# Day 38 validation commands

```bash
python -m sdetkit distribution-batch --format json --strict
python -m sdetkit distribution-batch --emit-pack-dir docs/artifacts/distribution-batch-pack --format json --strict
python -m sdetkit distribution-batch --execute --evidence-dir docs/artifacts/distribution-batch-pack/evidence --format json --strict
python scripts/check_distribution_batch_contract.py
```
