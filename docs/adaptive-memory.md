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

## Adaptive diagnosis learning loop

The local SQLite adaptive memory remains the repo-shape memory. Adaptive diagnosis outcomes use a JSONL learning loop so CI artifacts can be appended and reviewed without requiring database migrations.

Record an adaptive diagnosis artifact:

```bash
python -m sdetkit adaptive learn record build/adaptive-diagnosis.json \
  --db .sdetkit/adaptive-diagnosis-memory.jsonl
```

Summarize recurring diagnosis scenarios and weakest lanes:

```bash
python -m sdetkit adaptive learn summarize \
  --db .sdetkit/adaptive-diagnosis-memory.jsonl \
  --format json
```

Use the summary to pick the next follow-up: fix high-recurrence scenarios first, then add proof outcomes (`proof_passed`, `fix_accepted`, `false_positive`) as operators confirm or reject recommendations.


### Capturing operator feedback

The learning record command accepts outcome flags so confirmed or rejected recommendations affect the next summary:

```bash
python -m sdetkit adaptive learn record build/adaptive-diagnosis.json \
  --db .sdetkit/adaptive-diagnosis-memory.jsonl \
  --proof-passed \
  --fix-accepted
```

Use `--false-positive` to examplete a scenario when an operator confirms the diagnosis was wrong. The summarize command exposes calibration actions (`promote`, `examplete`, `increase_risk`, `lower_confidence`) per scenario and as a `calibration_summary` rollup.
