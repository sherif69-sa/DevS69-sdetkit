# Day 41 validation commands

```bash
python -m sdetkit expansion-automation --format json --strict
python -m sdetkit expansion-automation --emit-pack-dir docs/artifacts/expansion-automation-pack --format json --strict
python -m sdetkit expansion-automation --execute --evidence-dir docs/artifacts/expansion-automation-pack/evidence --format json --strict
python scripts/check_day41_expansion_automation_contract.py
```
