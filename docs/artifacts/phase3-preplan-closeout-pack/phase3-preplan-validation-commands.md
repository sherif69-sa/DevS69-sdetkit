# Day 59 validation commands

```bash
python -m sdetkit phase3-preplan-closeout --format json --strict
python -m sdetkit phase3-preplan-closeout --emit-pack-dir docs/artifacts/phase3-preplan-closeout-pack --format json --strict
python scripts/check_phase3_preplan_closeout_contract.py --skip-evidence
```
