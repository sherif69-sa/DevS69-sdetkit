# Cycle 65 validation commands

```bash
python -m sdetkit weekly-review-closeout --format json --strict
python -m sdetkit weekly-review-closeout --emit-pack-dir docs/artifacts/weekly-review-closeout-2-pack --format json --strict
python scripts/check_weekly_review_closeout_contract_2.py --skip-evidence
```
