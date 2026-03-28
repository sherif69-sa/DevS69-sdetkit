# Cycle 32 validation commands

```bash
python -m sdetkit release-cadence --format json --strict
python -m sdetkit release-cadence --emit-pack-dir docs/artifacts/release-cadence-pack --format json --strict
python -m sdetkit release-cadence --execute --evidence-dir docs/artifacts/release-cadence-pack/evidence --format json --strict
python scripts/check_release_cadence_contract.py
```
