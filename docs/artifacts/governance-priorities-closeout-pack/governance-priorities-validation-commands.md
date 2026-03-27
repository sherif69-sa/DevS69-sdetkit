# Day 88 validation commands

```bash
python -m sdetkit governance-priorities-closeout --format json --strict
python -m sdetkit governance-priorities-closeout --emit-pack-dir docs/artifacts/governance-priorities-closeout-pack --format json --strict
python scripts/check_governance_priorities_closeout_contract.py --skip-evidence
```
