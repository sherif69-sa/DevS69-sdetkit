# Day 28 validation commands

```bash
python -m sdetkit day28-weekly-review --format json --strict
python -m sdetkit day28-weekly-review --emit-pack-dir docs/artifacts/weekly-review-pack --format json --strict
python -m sdetkit day28-weekly-review --execute --evidence-dir docs/artifacts/weekly-review-pack/evidence --format json --strict
python scripts/check_weekly_review_contract.py
```
