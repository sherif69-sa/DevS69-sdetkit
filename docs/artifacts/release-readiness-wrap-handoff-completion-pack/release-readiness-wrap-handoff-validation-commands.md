#  validation commands

```bash
python -m sdetkit phase2-wrap-handoff-completion --format json --strict
python -m sdetkit phase2-wrap-handoff-completion --emit-pack-dir docs/artifacts/phase2-wrap-handoff-completion-pack --format json --strict
python scripts/check_phase2_wrap_handoff_completion_contract.py --skip-evidence
```
