# Cycle 74 validation commands

```bash
python -m sdetkit distribution-scaling-closeout --format json --strict
python -m sdetkit distribution-scaling-closeout --emit-pack-dir docs/artifacts/distribution-scaling-closeout-pack --format json --strict
python scripts/check_distribution_scaling_closeout_contract.py --skip-evidence
```
