# Deep Repo Index Engine (Wave 1)

The repo index engine builds deterministic local evidence for Adaptive Power Engine v2.

## What it does

- Crawls a local repository without network calls.
- Skips ignored directories (`.git`, `.venv`, `site`, caches, `node_modules`, `htmlcov`).
- Produces machine-readable evidence files for future boost scan v2, adaptive review, and patch planning.

## Commands

```bash
python -m sdetkit index build PATH --out build/sdetkit-index
python -m sdetkit index inspect build/sdetkit-index --format text
python -m sdetkit index inspect build/sdetkit-index --format operator-json
```

## Evidence files

- `build/sdetkit-index/index.json`
- `build/sdetkit-index/files.jsonl`
- `build/sdetkit-index/symbols.jsonl`
- `build/sdetkit-index/hotspots.jsonl`

Schema version: `sdetkit.index.v1`.

## Future feed-in

Wave 1 index evidence is the substrate for:

- boost scan v2 prioritization
- adaptive review planning
- deterministic operator reports
- source-to-test pairing hints and risk hotspot surfacing
