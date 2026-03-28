# Cycle 45 Validation Commands

```bash
python -m sdetkit expansion-closeout --format json --strict
python -m sdetkit expansion-closeout --emit-pack-dir docs/artifacts/expansion-closeout-pack --format json --strict
python scripts/check_expansion_closeout_contract.py --skip-evidence
```
