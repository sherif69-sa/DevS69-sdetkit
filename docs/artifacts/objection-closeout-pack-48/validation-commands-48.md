# Cycle 48 Validation Commands

```bash
python -m sdetkit objection-closeout --format json --strict
python -m sdetkit objection-closeout --emit-pack-dir docs/artifacts/objection-closeout-pack --format json --strict
python scripts/check_objection_closeout_contract.py --skip-evidence
```
