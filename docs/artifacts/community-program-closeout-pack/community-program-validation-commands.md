# Day 62 validation commands

```bash
python -m sdetkit community-program-closeout --format json --strict
python -m sdetkit community-program-closeout --emit-pack-dir docs/artifacts/community-program-closeout-pack --format json --strict
python scripts/check_community_program_closeout_contract.py --skip-evidence
```
