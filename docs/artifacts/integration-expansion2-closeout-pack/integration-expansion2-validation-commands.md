# Day 66 validation commands

```bash
python -m sdetkit integration-expansion2-closeout --format json --strict
python -m sdetkit integration-expansion2-closeout --emit-pack-dir docs/artifacts/integration-expansion2-closeout-pack --format json --strict
python scripts/check_integration_expansion2_closeout_contract.py --skip-evidence
```
