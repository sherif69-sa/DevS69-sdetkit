# Release Confidence KPI Pack

Use this weekly KPI pack to turn release-confidence improvements into a measurable operating loop.

## KPIs tracked

- **Time to first success** (minutes)
- **Lint debt trend** (issue count)
- **Type debt trend** (issue count)
- **CI cycle trend** (minutes)
- **Release gate pass trend** (pass rate)

## Command

```bash
python -m sdetkit kpi-report \
  --current build/kpi-metrics-current.json \
  --previous docs/artifacts/kpi-weekly/latest-kpi-pack.json \
  --week "$(date -u +%Y-%m-%d)" \
  --out-json build/release-confidence-kpi-pack.json \
  --out-md build/release-confidence-kpi-pack.md
```

## Weekly CI artifact

The `kpi-weekly.yml` workflow generates and uploads:

- `build/kpi-metrics-current.json`
- `build/release-confidence-kpi-pack.json`
- `build/release-confidence-kpi-pack.md`

Use these artifacts as the weekly baseline for continuous improvement decisions.
