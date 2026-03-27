# Day 65 validation commands

```bash
python -m sdetkit weekly-review-closeout --format json --strict
python -m sdetkit weekly-review-closeout --emit-pack-dir docs/artifacts/weekly-review-closeout-cycle2-pack --format json --strict
python scripts/check_day65_weekly_review_closeout_contract.py --skip-evidence
```
