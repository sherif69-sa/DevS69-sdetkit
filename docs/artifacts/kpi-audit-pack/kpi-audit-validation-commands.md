# Cycle 27 validation commands

```bash
python -m sdetkit kpi-audit --format json --strict
python -m sdetkit kpi-audit --emit-pack-dir docs/artifacts/kpi-audit-pack --format json --strict
python -m sdetkit kpi-audit --execute --evidence-dir docs/artifacts/kpi-audit-pack/evidence --format json --strict
python scripts/check_kpi_audit_contract.py
```
