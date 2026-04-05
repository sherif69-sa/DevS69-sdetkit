# Day 68 validation commands

```bash
python -m sdetkit integration-expansion4-closeout --format json --strict
python -m sdetkit integration-expansion4-closeout --emit-pack-dir docs/artifacts/integration-expansion4-closeout-pack --format json --strict
python scripts/check_integration_expansion4_closeout_contract.py --skip-evidence
```
