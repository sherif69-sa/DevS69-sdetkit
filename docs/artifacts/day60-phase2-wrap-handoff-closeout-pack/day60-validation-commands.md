# Day 60 validation commands

```bash
python -m sdetkit day60-phase2-wrap-handoff-closeout --format json --strict
python -m sdetkit day60-phase2-wrap-handoff-closeout --emit-pack-dir docs/artifacts/day60-phase2-wrap-handoff-closeout-pack --format json --strict
python scripts/check_day60_phase2_wrap_handoff_closeout_contract.py --skip-evidence
```
