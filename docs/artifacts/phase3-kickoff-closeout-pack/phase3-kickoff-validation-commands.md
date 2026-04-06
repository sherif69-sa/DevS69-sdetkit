#  validation commands

```bash
python -m sdetkit phase3-kickoff-closeout --format json --strict
python -m sdetkit phase3-kickoff-closeout --emit-pack-dir docs/artifacts/phase3-kickoff-closeout-pack --format json --strict
python scripts/check_phase3_kickoff_closeout_contract.py --skip-evidence
```
