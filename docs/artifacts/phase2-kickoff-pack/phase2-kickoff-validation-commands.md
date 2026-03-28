# Cycle 31 validation commands

```bash
python -m sdetkit phase2-kickoff --format json --strict
python -m sdetkit phase2-kickoff --emit-pack-dir docs/artifacts/phase2-kickoff-pack --format json --strict
python -m sdetkit phase2-kickoff --execute --evidence-dir docs/artifacts/phase2-kickoff-pack/evidence --format json --strict
python scripts/check_phase2_kickoff_contract.py
```
