# Benchmark Control Regression Gate

The benchmark control regression gate compares a generated benchmark control
scorecard with an explicit repository baseline.

The bootstrap baseline lives at:

```text
.sdetkit/benchmark-control-baseline.json
```

That location follows the repository's existing deterministic, offline
baseline convention.

## Baseline activation contract

The baseline declares:

```text
activation.model=protected_main_merge
activation.requires_human_review=true
activation.automatic_updates_allowed=false
```

The bootstrap baseline becomes authoritative only after its pull request is
reviewed and merged into protected `main`. Later baseline changes require the
same reviewed repository-change path. The command never rewrites the baseline.

## Run the comparison

```bash
python -m sdetkit.benchmark_control_regression_gate \
  --scorecard build/benchmark-control-scorecard/benchmark-control-scorecard.json \
  --baseline .sdetkit/benchmark-control-baseline.json \
  --out-dir build/benchmark-control-regression-gate \
  --format json
```

The command writes:

- `benchmark-control-regression.json`
- `benchmark-control-regression.md`

## Exit codes

| Exit code | Meaning |
|---:|---|
| `0` | The candidate satisfies the reviewed baseline |
| `1` | A measurable regression was detected |
| `2` | The scorecard or baseline input is invalid |

## Regression dimensions

The gate checks:

- scorecard schema and passing status;
- minimum overall score;
- minimum score for every reviewed dimension;
- minimum report and scenario coverage;
- minimum scenario pass rate;
- required benchmark modes;
- absence of expanded authority fields;
- exact preservation of the reviewed decision boundary.

## Authority boundary

This slice adds a deterministic comparison command and artifact only. It does
not wire the command into required CI.

```text
reporting_only=true
current_pr_decision_input=false
execution_allowed=false
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
executes_plan=false
executes_patch=false
```

A failed comparison requires human review. It does not authorize a baseline
update, code change, automation action, or merge.
