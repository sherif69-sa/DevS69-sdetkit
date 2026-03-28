# Lane — Demo asset #1 production

Lane closes the first distribution-ready demo asset, turning Lane release readiness into externally consumable proof.

## Why Lane matters

- Demonstrates real value with a concise `doctor` workflow narrative.
- Creates a repeatable media pipeline (script → cut → publish → evidence).
- Links each demo claim to runnable CLI commands and docs for trust.

## Required inputs (Lane)

- `docs/artifacts/release-cadence-pack/release-cadence-summary.json`
- `docs/artifacts/release-cadence-pack/release-delivery-board.md`

## Lane command lane

```bash
python -m sdetkit demo-asset --format json --strict
python -m sdetkit demo-asset --emit-pack-dir docs/artifacts/demo-asset-pack --format json --strict
python -m sdetkit demo-asset --execute --evidence-dir docs/artifacts/demo-asset-pack/evidence --format json --strict
python scripts/check_demo_asset_contract.py
```

## Demo production contract

- Demo owner: one accountable editor and one backup reviewer are assigned.
- Target format: publish both MP4 clip and GIF teaser for social/docs embedding.
- Runtime SLA: main demo duration stays between 45 and 90 seconds.
- Narrative shape: pain -> command -> output -> value CTA must appear in order.

## Demo quality checklist

- [ ] Shows `python -m sdetkit doctor --json` execution with readable terminal output
- [ ] Includes before/after or problem/solution framing in first 10 seconds
- [ ] Mentions one measurable trust signal (time saved, failures prevented, or coverage)
- [ ] Includes docs link and CLI command in caption or description
- [ ] Raw source file and final export are both stored in artifact pack

## Lane delivery board

- [ ] Lane script draft committed
- [ ] Lane first cut rendered
- [ ] Lane final cut + caption copy approved
- [ ] Lane demo asset #2 backlog pre-scoped
- [ ] Lane KPI instrumentation plan updated

## Scoring model

Lane weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 35 points.
- Demo contract lock + delivery board readiness: 15 points.
