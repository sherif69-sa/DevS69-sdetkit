# Name 31 validation commands

```bash
python -m sdetkit name31-phase2-kickoff --format json --strict
python -m sdetkit name31-phase2-kickoff --emit-pack-dir docs/artifacts/name31-phase2-pack --format json --strict
python -m sdetkit name31-phase2-kickoff --execute --evidence-dir docs/artifacts/name31-phase2-pack/evidence --format json --strict
python scripts/check_name31_phase2_kickoff_contract.py
```
