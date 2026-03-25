# Release readiness validation commands

```bash
python -m sdetkit release-readiness --format json --strict
python -m sdetkit release-readiness --emit-pack-dir docs/artifacts/release-readiness-pack --format json --strict
python -m sdetkit release-readiness --execute --evidence-dir docs/artifacts/release-readiness-pack/evidence --format json --strict
python scripts/check_release_readiness_contract.py
```
