# Day 28 validation commands

```bash
python -m sdetkit day28-weekly-review --format json --strict
python -m sdetkit day28-weekly-review --emit-pack-dir docs/artifacts/day28-weekly-pack --format json --strict
python -m sdetkit day28-weekly-review --execute --evidence-dir docs/artifacts/day28-weekly-pack/evidence --format json --strict
python scripts/check_day28_weekly_review_contract.py
```
