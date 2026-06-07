#  validation commands

```bash
python -m sdetkit integration-expansion3-completion --format json --strict
python -m sdetkit integration-expansion3-completion --emit-pack-dir docs/artifacts/integration-expansion3-completion-pack --format json --strict
python scripts/check_integration_expansion3_completion_contract.py --skip-evidence
```
