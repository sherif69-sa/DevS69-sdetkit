# Day 64 validation commands

```bash
python -m sdetkit integration-expansion-closeout --format json --strict
python -m sdetkit integration-expansion-closeout --emit-pack-dir docs/artifacts/integration-expansion-closeout-pack --format json --strict
python scripts/check_integration_expansion_closeout_contract.py --skip-evidence
```
