# Day 41 validation commands

```bash
python -m sdetkit day41-expansion-automation --format json --strict
python -m sdetkit day41-expansion-automation --emit-pack-dir docs/artifacts/day41-expansion-automation-pack --format json --strict
python -m sdetkit day41-expansion-automation --execute --evidence-dir docs/artifacts/day41-expansion-automation-pack/evidence --format json --strict
python scripts/check_day41_expansion_automation_contract.py
```
