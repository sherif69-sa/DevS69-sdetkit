# Day 20 validation commands

```bash
python -m sdetkit release-narrative --format json --strict
python -m sdetkit release-narrative --emit-pack-dir docs/artifacts/day20-release-narrative-pack --format json --strict
python -m sdetkit release-narrative --execute --evidence-dir docs/artifacts/day20-release-narrative-pack/evidence --format json --strict
python scripts/check_day20_release_narrative_contract.py
```
