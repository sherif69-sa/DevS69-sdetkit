# First-proof learning database and adaptive reviewer alignment

The first-proof lane now builds a local learning database and adaptive review rollup so every run improves repository-level guidance.

## Artifacts

After `make first-proof-verify`, the following are produced:

- `build/first-proof/first-proof-summary.json`
- `build/first-proof/first-proof-learning-db.jsonl`
- `build/first-proof/first-proof-learning-rollup.json`
- `build/first-proof/control-tower.json`
- `build/first-proof/control-tower.md`
- `build/first-proof/weekly-trend.json`
- `build/first-proof/weekly-trend.md`
- `build/first-proof/weekly-threshold-check.json`

## What this enables

- A growing run history (`*.jsonl`) that captures decision trend and failing step patterns.
- Adaptive reviewer action guidance in the rollup under `adaptive_reviewer.actions`.
- Predictable, repeatable, and parallel-safe optimization loop for the repo.

## Commands

```bash
make first-proof-verify
```

Integrate with adaptive reviewer postcheck:

```bash
python scripts/adaptive_postcheck.py . --scenario strict --out build/adaptive-postcheck-strict.json
```

The adaptive postcheck now evaluates first-proof learning thresholds (minimum runs + SHIP rate)
and emits follow-up enhancements when trend is below target. Weekly threshold checks also support
consecutive NO-SHIP gating for better signal quality.

Threshold profiles are branch-aware via `config/first_proof_threshold_profiles.json`
(`main`/`release` can enforce `fail_on_breach: true`, while `default` remains non-blocking).

When threshold breach is `true`, owner escalation can now be generated with branch-aware
SLA/owner routing via `config/first_proof_owner_escalation_profiles.json`:

```bash
make owner-escalation-payload
```

This consumes `build/first-proof/weekly-threshold-check.json` and escalates with stricter
SLA on protected branches (`main`, `release`).

or directly:

```bash
python scripts/first_proof_learning_db.py \
  --summary build/first-proof/first-proof-summary.json \
  --db build/first-proof/first-proof-learning-db.jsonl \
  --rollup-out build/first-proof/first-proof-learning-rollup.json \
  --format json
```

## Operating model

1. Run first-proof.
2. Validate summary contract.
3. Append snapshot to learning DB.
4. Generate adaptive reviewer rollup actions.
5. Build control-tower summary artifact for operator review.
6. Build weekly trend artifact (last-7 run ship rate + adaptive confidence).
7. Run threshold check to detect sustained trend regressions.
8. Use top failed steps and action list to prioritize fixes.
