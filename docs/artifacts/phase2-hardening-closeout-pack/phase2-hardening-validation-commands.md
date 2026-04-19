#  validation commands

```bash
python -m sdetkit phase2-hardening-closeout --format json --strict
python -m sdetkit phase2-hardening-closeout --emit-pack-dir docs/artifacts/phase2-hardening-closeout-pack --format json --strict
python scripts/check_phase2_hardening_closeout_contract.py --skip-evidence
```
