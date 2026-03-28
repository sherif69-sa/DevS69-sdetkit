# Cycle 85 validation commands

```bash
python -m sdetkit release-prioritization-closeout --format json --strict
python -m sdetkit release-prioritization-closeout --emit-pack-dir docs/artifacts/release-prioritization-closeout-pack --format json --strict
python scripts/check_release_prioritization_closeout_contract.py --skip-evidence
```
