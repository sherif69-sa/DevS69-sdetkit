# Ecosystem priorities validation commands

```bash
python -m sdetkit ecosystem-priorities-closeout --format json --strict
python -m sdetkit ecosystem-priorities-closeout --emit-pack-dir docs/artifacts/ecosystem-priorities-closeout-pack --format json --strict
python scripts/check_day78_ecosystem_priorities_closeout_contract.py --skip-evidence
```
