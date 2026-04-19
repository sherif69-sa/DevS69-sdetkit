#  validation commands

```bash
python -m sdetkit phase2-wrap-handoff-closeout --format json --strict
python -m sdetkit phase2-wrap-handoff-closeout --emit-pack-dir docs/artifacts/phase2-wrap-handoff-closeout-pack --format json --strict
python scripts/check_phase2_wrap_handoff_closeout_contract.py --skip-evidence
```
