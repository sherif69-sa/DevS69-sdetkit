# Day 20 validation commands

```bash
python -m sdetkit release-communications --format json --strict
python -m sdetkit release-communications --emit-pack-dir docs/artifacts/release-communications-pack --format json --strict
python -m sdetkit release-communications --execute --evidence-dir docs/artifacts/release-communications-pack/evidence --format json --strict
python scripts/check_day20_release_narrative_contract.py
```
