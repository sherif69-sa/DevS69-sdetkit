#  validation commands

```bash
python -m sdetkit contributor-recognition-closeout --format json --strict
python -m sdetkit contributor-recognition-closeout --emit-pack-dir docs/artifacts/contributor-recognition-closeout-pack --format json --strict
python scripts/check_contributor_recognition_closeout_contract.py --skip-evidence
```
