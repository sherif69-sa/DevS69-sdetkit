# Day 87 validation commands

```bash
python -m sdetkit day87-governance-handoff-closeout --format json --strict
python -m sdetkit day87-governance-handoff-closeout --emit-pack-dir docs/artifacts/day87-governance-handoff-closeout-pack --format json --strict
python scripts/check_day87_governance_handoff_closeout_contract.py --skip-evidence
```
