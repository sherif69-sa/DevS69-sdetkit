# Day 35 validation commands

```bash
python -m sdetkit day35-kpi-instrumentation --format json --strict
python -m sdetkit day35-kpi-instrumentation --emit-pack-dir docs/artifacts/kpi-instrumentation-pack --format json --strict
python -m sdetkit day35-kpi-instrumentation --execute --evidence-dir docs/artifacts/kpi-instrumentation-pack/evidence --format json --strict
python scripts/check_kpi_instrumentation_contract.py
```
