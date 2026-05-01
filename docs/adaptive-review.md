# Adaptive Review v2

Adaptive review augments `sdetkit review` with repo-specific signals from:
- five-head posture (`sdetkit.review.five-heads.v1`)
- repo index (`sdetkit.index.v1`)
- adaptive SQLite memory (`sdetkit.adaptive.memory.v1`)
- boost scan v2 (`sdetkit.boost.scan.v2`)

It is local-only: no network calls, no external services, and no secrets required.

## Commands

- `python -m sdetkit review . --adaptive --deep --learn --db .sdetkit/adaptive.db --format operator-json`
- `python -m sdetkit review . --adaptive --deep --learn --db .sdetkit/adaptive.db --evidence-dir build/adaptive-review --format text`

## Notes

- Adaptive payload schema: `sdetkit.review.adaptive.v1` in `operator-json` under `adaptive_review`.
- Existing non-adaptive review output remains unchanged.
- Do not commit `.db` files or generated evidence artifacts.
