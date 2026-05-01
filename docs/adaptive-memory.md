# Adaptive SQLite memory (Wave 2 foundation)

SDETKit Adaptive Power Engine v2 Wave 2 adds a local SQLite memory layer that stores deterministic index intelligence across runs.

## Purpose

- Persist local repo scan history so recurring risks can be ranked over time.
- Store file/symbol/hotspot snapshots and derived risk events.
- Provide explainable history for future Boost Scan v2 and Adaptive Review v2.

## Safety and posture

- Local-only SQLite database.
- No network calls.
- No external services.
- No secrets required or transmitted.

## Commands

```bash
python -m sdetkit adaptive init --db .sdetkit/adaptive.db
python -m sdetkit adaptive ingest build/sdetkit-index/index.json --db .sdetkit/adaptive.db
python -m sdetkit adaptive history --db .sdetkit/adaptive.db --format text
python -m sdetkit adaptive history --db .sdetkit/adaptive.db --format operator-json
python -m sdetkit adaptive explain PATH --db .sdetkit/adaptive.db --format text
python -m sdetkit adaptive explain PATH --db .sdetkit/adaptive.db --format operator-json
```

Schema version: `sdetkit.adaptive.memory.v1`.

## Tables

- `schema_meta`: schema version metadata.
- `runs`: ingest run summary (root, scanned file/line counts, source path).
- `files`: indexed file rollup per run.
- `symbols`: extracted symbol rollup per run.
- `hotspots`: hotspot rollup per run.
- `risk_events`: derived recurring risk keys from hotspots.
- `recommendations`: derived prioritized follow-up actions.

## Output contract notes

- `operator-json` is stable and machine-readable.
- `history` includes run counts, latest run, totals, top risk files, and recommendations.
- `explain` includes recurring hotspot evidence scoped to a target path and recommended next actions.

## Git hygiene

Adaptive DB files are generated local artifacts. Do not commit `.db` outputs or build evidence.
