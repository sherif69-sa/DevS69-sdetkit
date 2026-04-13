# Legacy burn-down program

The legacy burn-down report turns `legacy_command_analyzer` output into a measurable weekly backlog KPI.

## Generate

```bash
python scripts/legacy_burndown.py \
  --current .sdetkit/out/legacy-command-analyzer.json \
  --baseline .sdetkit/out/legacy-command-analyzer.baseline.json \
  --baseline-from-history .sdetkit/out/legacy-history \
  --target-reduction-pct 10 \
  --format json
```

Outputs:

- JSON contract: `.sdetkit/out/legacy-burndown.json`
- Markdown summary: `.sdetkit/out/legacy-burndown.md`
- CSV KPI digest: `.sdetkit/out/legacy-burndown.csv`

## JSON contract

- `schema_version`: `1`
- `source_contract`: `sdetkit.legacy.burndown.v1`
- `totals`: baseline/current/delta/reduction percent
- `weekly_kpi`: target percentage + target-met flag
- `groups.current` and `groups.baseline`:
  - `category`
  - `path`
  - `domain`

All object keys are sorted for deterministic outputs.
