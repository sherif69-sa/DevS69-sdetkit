# Mission Control Doctor Cortex trend

Mission Control Doctor Cortex trend summarizes Doctor Cortex health across a Mission Control run ledger.

```bash
python -m sdetkit.mission_control_cortex_trend \
  --ledger-path .sdetkit/runs/mission-control-runs.jsonl \
  --format text
```

JSON and Markdown are also available:

```bash
python -m sdetkit.mission_control_cortex_trend \
  --ledger-path .sdetkit/runs/mission-control-runs.jsonl \
  --format json \
  --out build/doctor-cortex-trend.json

python -m sdetkit.mission_control_cortex_trend \
  --ledger-path .sdetkit/runs/mission-control-runs.jsonl \
  --format md \
  --out build/doctor-cortex-trend.md
```

The trend output is public-safe. It includes counts, statuses, trend direction, and run ids. It redacts the ledger path and does not emit raw doctor evidence, raw fix text, command lists, source paths, or artifact paths.

The analyzer can read Doctor Cortex summaries embedded in future ledger records. For existing records, it can load `mission-control.json` from each record's artifact directory and extract the summary from the bundle.
