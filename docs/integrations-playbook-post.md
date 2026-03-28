# Lane — Playbook post #1

Lane publishes playbook post #1 that converts Lane distribution evidence into a reusable operator guide.

## Why Lane matters

- Converts Lane distribution evidence into a reusable post + playbook operating pattern.
- Preserves quality by enforcing owner accountability, CTA integrity, and KPI targets.
- Creates a deterministic handoff from publication outcomes into Lane scale priorities.

## Required inputs (Lane)

- `docs/artifacts/distribution-batch-pack/distribution-batch-summary.json`
- `docs/artifacts/distribution-batch-pack/delivery-board.md`

## Lane command lane

```bash
python -m sdetkit playbook-post --format json --strict
python -m sdetkit playbook-post --emit-pack-dir docs/artifacts/playbook-post-pack --format json --strict
python -m sdetkit playbook-post --execute --evidence-dir docs/artifacts/playbook-post-pack/evidence --format json --strict
python scripts/check_playbook_post_contract.py
```

## Playbook publication contract

- Single owner + backup reviewer are assigned for Lane playbook publication and metric follow-up.
- The Lane playbook post references Lane distribution winners and explicit misses.
- Every Lane playbook section includes docs CTA, runnable command CTA, and one KPI target.
- Lane closeout records publication learnings and Lane scale priorities.

## Playbook quality checklist

- [ ] Includes executive summary, tactical checklist, and rollout timeline
- [ ] Every section has owner, publish window, and KPI target
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures baseline, current, and delta for each playbook KPI
- [ ] Artifact pack includes playbook draft, rollout plan, scorecard, and execution log

## Lane delivery board

- [ ] Lane playbook draft committed
- [ ] Lane review notes captured with owner + backup
- [ ] Lane rollout timeline exported
- [ ] Lane KPI scorecard snapshot exported
- [ ] Lane scale priorities drafted from Lane learnings

## Scoring model

Lane weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Lane continuity and strict baseline carryover: 35 points.
- Publication contract lock + delivery board readiness: 15 points.
