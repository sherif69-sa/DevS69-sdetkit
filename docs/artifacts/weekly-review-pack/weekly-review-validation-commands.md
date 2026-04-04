# Day 28 validation commands

```bash
python -m sdetkit weekly-review-lane --format json --strict
python -m sdetkit weekly-review-lane --emit-pack-dir docs/artifacts/weekly-review-pack --format json --strict
python -m sdetkit weekly-review-lane --execute --evidence-dir docs/artifacts/weekly-review-pack/evidence --format json --strict
python scripts/check_weekly_review_contract.py
```
