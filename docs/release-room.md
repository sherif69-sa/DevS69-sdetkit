# Release Room Execution Planner

`python -m sdetkit release-room plan PATH` builds a concise local operator plan by combining:
- index inspect (`sdetkit.index.v1`)
- boost scan v2 (`sdetkit.boost.scan.v2`)
- adaptive review v2 (`sdetkit.review.adaptive.v1`)
- adaptive memory history/explain (`sdetkit.adaptive.memory.v1`)
- repo check signals when available

## Local-only posture
- No network calls.
- No external services.
- Deterministic operator JSON schema: `sdetkit.release_room.plan.v1`.

## Usage
```bash
python -m sdetkit release-room plan . --deep --learn --db .sdetkit/adaptive.db --max-lines 100 --format text
python -m sdetkit release-room plan . --deep --learn --db .sdetkit/adaptive.db --format operator-json
python -m sdetkit release-room plan . --deep --learn --db .sdetkit/adaptive.db --evidence-dir build/release-room --format operator-json
```

## Decision semantics
- `SHIP`: clean repo check, no severe blockers, healthy boost score.
- `REVIEW`: non-ship risk context exists but patch candidates are available.
- `NO-SHIP`: severe blockers, invalid helper output, or repo findings.
- `UNKNOWN`: required evidence cannot be parsed.

## Evidence outputs
When `--evidence-dir` is provided, the planner writes JSON/TXT evidence there only. Avoid committing generated DB/evidence artifacts.
