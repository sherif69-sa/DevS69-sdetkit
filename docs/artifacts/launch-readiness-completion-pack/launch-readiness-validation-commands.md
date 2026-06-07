#  validation commands

```bash
python -m sdetkit launch-readiness-completion --format json --strict
python -m sdetkit launch-readiness-completion --emit-pack-dir docs/artifacts/launch-readiness-completion-pack --format json --strict
python scripts/check_launch_readiness_completion_contract.py --skip-evidence
```
