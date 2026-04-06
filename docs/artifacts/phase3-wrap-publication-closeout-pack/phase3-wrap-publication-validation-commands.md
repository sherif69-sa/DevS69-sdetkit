#  validation commands

```bash
python -m sdetkit phase3-wrap-publication-closeout --format json --strict
python -m sdetkit phase3-wrap-publication-closeout --emit-pack-dir docs/artifacts/phase3-wrap-publication-closeout-pack --format json --strict
python scripts/check_phase3_wrap_publication_closeout_contract.py --skip-evidence
```
