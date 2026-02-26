# Day 34 — Demo asset #2 production (repo audit)

Day 34 closes the second distribution-ready demo asset by translating repository audit signals into clear, actionable proof.

## Why Day 34 matters

- Shows a practical `repo audit` workflow that teams can run immediately.
- Reinforces repeatable media operations (script → cut → publish → evidence).
- Increases trust by linking findings to remediation recommendations and docs.

## Required inputs (Day 33)

- `docs/artifacts/day33-demo-asset-pack/day33-demo-asset-summary.json`
- `docs/artifacts/day33-demo-asset-pack/day33-delivery-board.md`

## Day 34 command lane

```bash
python -m sdetkit day34-demo-asset2 --format json --strict
python -m sdetkit day34-demo-asset2 --emit-pack-dir docs/artifacts/day34-demo-asset2-pack --format json --strict
python -m sdetkit day34-demo-asset2 --execute --evidence-dir docs/artifacts/day34-demo-asset2-pack/evidence --format json --strict
python scripts/check_day34_demo_asset2_contract.py
```

## Repo-audit production contract

- Demo owner: one accountable editor and one backup reviewer are assigned.
- Target format: publish both MP4 clip and GIF teaser for social/docs embedding.
- Runtime SLA: main demo duration stays between 60 and 120 seconds.
- Narrative shape: repo risk -> audit command -> findings -> remediation CTA must appear in order.

## Repo-audit quality checklist

- [ ] Shows `python -m sdetkit repo audit --json` execution with readable terminal output
- [ ] Highlights at least two findings with one remediation recommendation
- [ ] Mentions one measurable trust signal (time saved, failures prevented, or coverage)
- [ ] Includes docs link and CLI command in caption or description
- [ ] Raw source file and final export are both stored in artifact pack

## Day 34 delivery board

- [ ] Day 34 script draft committed
- [ ] Day 34 first cut rendered
- [ ] Day 34 final cut + caption copy approved
- [ ] Day 35 KPI instrumentation backlog pre-scoped
- [ ] Day 36 community distribution plan updated

## Scoring model

Day 34 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Day 33 continuity and strict baseline carryover: 35 points.
- Repo-audit contract lock + delivery board readiness: 15 points.
