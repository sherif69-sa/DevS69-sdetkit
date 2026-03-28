# Name 35 validation commands

```bash
python -m sdetkit name35-kpi-instrumentation --format json --strict
python -m sdetkit name35-kpi-instrumentation --emit-pack-dir docs/artifacts/name35-kpi-instrumentation-pack --format json --strict
python -m sdetkit name35-kpi-instrumentation --execute --evidence-dir docs/artifacts/name35-kpi-instrumentation-pack/evidence --format json --strict
python scripts/check_name35_kpi_instrumentation_contract.py
```
