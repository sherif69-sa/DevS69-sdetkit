# Cycle 52 Validation Commands

```bash
python -m sdetkit cycle52-narrative-closeout --format json --strict
python -m sdetkit cycle52-narrative-closeout --emit-pack-dir docs/artifacts/narrative-closeout-pack --format json --strict
python scripts/check_narrative_closeout_contract.py --skip-evidence
```
