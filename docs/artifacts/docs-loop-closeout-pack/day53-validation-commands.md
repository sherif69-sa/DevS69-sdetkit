# Day 53 Validation Commands

```bash
python -m sdetkit docs-loop-closeout --format json --strict
python -m sdetkit docs-loop-closeout --emit-pack-dir docs/artifacts/docs-loop-closeout-pack --format json --strict
python scripts/check_docs_loop_closeout_contract.py --skip-evidence
```
