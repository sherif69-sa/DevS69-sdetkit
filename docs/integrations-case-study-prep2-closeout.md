# Lane — Case-study prep #2 closeout lane

Lane closes with a major upgrade that turns Lane integration outputs into a measurable triage-speed case-study prep pack.

## Why Case Study Prep 2 Closeout matters

- Converts Lane implementation signals into before/after triage-speed evidence.
- Protects case-study quality with strict contract coverage, runnable commands, and rollback safety.
- Creates a deterministic handoff from Lane case-study prep #2 to Lane case-study prep #3.

## Required inputs (Lane)

- `docs/artifacts/case-study-prep1-closeout-pack/case-study-prep1-closeout-summary.json`
- `docs/artifacts/case-study-prep1-closeout-pack/case-study-prep1-delivery-board.md`
- `docs/roadmap/plans/triage-speed-case-study.json`

## Case Study Prep 2 Closeout command lane (Legacy Lane)

```bash
python -m sdetkit case-study-prep2-closeout --format json --strict
python -m sdetkit case-study-prep2-closeout --emit-pack-dir docs/artifacts/case-study-prep2-closeout-pack --format json --strict
python -m sdetkit case-study-prep2-closeout --execute --evidence-dir docs/artifacts/case-study-prep2-closeout-pack/evidence --format json --strict
python scripts/check_case_study_prep2_closeout_contract.py
```

## Case-study prep contract

- Single owner + backup reviewer are assigned for Lane triage-speed case-study prep and signoff.
- The Lane lane references Lane case-study prep outputs, governance decisions, and KPI continuity signals.
- Every Lane section includes docs CTA, runnable command CTA, KPI threshold, and rollback guardrail.
- Lane closeout records before/after triage-speed deltas, evidence confidence notes, and Lane prep priorities.

## Case-study quality checklist

- [ ] Includes baseline window, treatment window, and outlier handling notes
- [ ] Every section has owner, review window, KPI threshold, and risk flag
- [ ] CTA links point to docs + runnable command evidence
- [ ] Scorecard captures failure-rate delta, MTTR delta, confidence, and rollback owner
- [ ] Artifact pack includes integration brief, case-study narrative, controls log, KPI scorecard, and execution log

## Case Study Prep 2 Closeout delivery board (Legacy Lane)

- [ ] Lane integration brief committed
- [ ] Lane triage-speed case-study narrative published
- [ ] Lane controls and assumptions log exported
- [ ] Lane KPI scorecard snapshot exported
- [ ] Lane case-study prep priorities drafted from Lane learnings

## Scoring model

Lane weighted score (0-100):

- Contract + command lane integrity (35)
- Lane continuity baseline quality (35)
- Triage-speed evidence data + delivery board completeness (30)

Strict pass requires score >= 95 and zero critical failures.
