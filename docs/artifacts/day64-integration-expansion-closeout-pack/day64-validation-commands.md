# Day 64 validation commands

```bash
python -m sdetkit day64-integration-expansion-closeout --format json --strict
python -m sdetkit day64-integration-expansion-closeout --emit-pack-dir docs/artifacts/day64-integration-expansion-closeout-pack --format json --strict
python scripts/check_day64_integration_expansion_closeout_contract.py --skip-evidence
```
