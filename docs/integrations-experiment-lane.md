# Cycle 37 — Experiment lane activation

Cycle 37 turns Cycle 36 distribution misses into controlled experiments with strict scoring, owner accountability, and Cycle 38 rollout decisions.

## Why Cycle 37 matters

- Converts distribution misses into measurable learnings instead of ad-hoc retries.
- Protects quality by coupling growth experiments to reliability and contribution guardrails.
- Creates a deterministic handoff from experiment outcomes into Cycle 38 distribution actions.

## Required inputs (Cycle 36)

- `docs/artifacts/distribution-closeout-pack/distribution-closeout-summary.json`
- `docs/artifacts/distribution-closeout-pack/delivery-board.md`

## Cycle 37 command lane

```bash
python -m sdetkit experiment-lane --format json --strict
python -m sdetkit experiment-lane --emit-pack-dir docs/artifacts/experiment-lane-pack --format json --strict
python -m sdetkit experiment-lane --execute --evidence-dir docs/artifacts/experiment-lane-pack/evidence --format json --strict
python scripts/check_experiment_lane_contract.py
```

## Experiment contract

- Single owner + backup reviewer are assigned for experiment execution and decision logging.
- At least three experiments include hypothesis, KPI target delta, and stop/continue threshold.
- Every experiment is linked to one Cycle 36 distribution miss with explicit remediation intent.
- Cycle 37 report commits Cycle 38 distribution batch actions based on experiment outcomes.

## Experiment quality checklist

- [ ] Includes at least three experiments with control vs variant definitions
- [ ] Every experiment has KPI target, owner, and decision deadline
- [ ] Guardrail metrics include reliability and contribution-quality checks
- [ ] Experiment scorecard records baseline, current, and delta fields
- [ ] Artifact pack includes matrix, hypothesis brief, scorecard, and decision log

## Cycle 37 delivery board

- [ ] Cycle 37 experiment matrix committed
- [ ] Cycle 37 hypothesis brief reviewed with owner + backup
- [ ] Cycle 37 scorecard snapshot exported
- [ ] Cycle 38 distribution batch actions selected from winners
- [ ] Cycle 38 fallback plan documented for losing variants

## Scoring model

Cycle 37 weighted score (0-100):

- Docs contract + command lane completeness: 30 points.
- Discoverability alignment (README/docs index/top-10): 20 points.
- Cycle 36 continuity and strict baseline carryover: 35 points.
- Experiment contract lock + delivery board readiness: 15 points.
