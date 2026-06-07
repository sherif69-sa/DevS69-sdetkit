#  validation commands

```bash
python -m sdetkit integration-expansion2-completion --format json --strict
python -m sdetkit integration-expansion2-completion --emit-pack-dir docs/artifacts/integration-expansion2-completion-pack --format json --strict
python scripts/check_integration_expansion2_completion_contract.py --skip-evidence
```
