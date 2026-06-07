#  validation commands

```bash
python -m sdetkit integration-expansion4-completion --format json --strict
python -m sdetkit integration-expansion4-completion --emit-pack-dir docs/artifacts/integration-expansion4-completion-pack --format json --strict
python scripts/check_integration_expansion4_completion_contract.py --skip-evidence
```
