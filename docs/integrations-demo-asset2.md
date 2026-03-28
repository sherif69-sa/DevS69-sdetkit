# Cycle 34 — Demo asset #2 production (repo audit)

Cycle 34 closes the second distribution-ready demo asset by translating repository audit signals into clear, actionable proof.

## Why Cycle 34 matters

- Shows a practical `repo audit` workflow that teams can run immediately.
- Reinforces repeatable media operations (script → cut → publish → evidence).
- Increases trust by linking findings to remediation recommendations and docs.

## Required inputs (Cycle 33)

- `docs/artifacts/demo-asset-pack/demo-asset-summary.json`
- `docs/artifacts/demo-asset-pack/demo-delivery-board.md`

## Cycle 34 command lane

```bash
python -m sdetkit demo-asset2 --format json --strict
python -m sdetkit demo-asset2 --emit-pack-dir docs/artifacts/demo-asset2-pack --format json --strict
python -m sdetkit demo-asset2 --execute --evidence-dir docs/artifacts/demo-asset2-pack/evidence --format json --strict
python scripts/check_demo_asset2_contract.py
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

## Cycle 34 delivery board

- [ ] Cycle 34 script draft committed
- [ ] Cycle 34 first cut rendered
- [ ] Cycle 34 final cut + caption copy approved
- [ ] Cycle 35 KPI instrumentation backlog pre-scoped
- [ ] Cycle 36 community distribution plan updated

## Scoring model

Cycle 34 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Cycle 33 continuity and strict baseline carryover: 35 points.
- Repo-audit contract lock + delivery board readiness: 15 points.
