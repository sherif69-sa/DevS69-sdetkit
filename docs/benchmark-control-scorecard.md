# Benchmark Control Scorecard

The benchmark control scorecard aggregates multiple replayable benchmark
reports into one deterministic, reporting-only view.

It exists to make the benchmark program easier to operate before any baseline
regression policy is introduced.

## Inputs

Pass one or more replayable benchmark reports:

```bash
python -m sdetkit.benchmark_control_scorecard \
  --benchmark-report build/benchmark-a/benchmark-report.json \
  --benchmark-report build/benchmark-b/benchmark-report.json \
  --out-dir build/benchmark-control-scorecard \
  --format json
```

Each report must expose:

- a schema version and status;
- internally consistent scenario counts;
- a required-contract result;
- a safety boundary with `preserved=true`.

Duplicate schema/mode identities are rejected so the same benchmark surface
cannot be counted twice.

## Score dimensions

The overall score is the arithmetic mean of four transparent percentages:

| Dimension | Meaning |
|---|---|
| `report_status` | Fraction of input reports whose status is `passed` |
| `scenario_health` | Aggregate passed scenarios divided by total scenarios |
| `required_contracts` | Fraction of reports whose required scenarios are present and passing |
| `safety_boundaries` | Fraction of reports with preserved, non-expanding authority boundaries |

A scorecard passes only when every dimension is `100`, there is at least one
scenario, and no scenario failed.

## Outputs

The command writes:

- `benchmark-control-scorecard.json`
- `benchmark-control-scorecard.md`

The JSON artifact is suitable for the next tranche slice: explicit,
reviewed-baseline comparison.

## Authority boundary

The scorecard is observational.

```text
reporting_only=true
current_pr_decision_input=false
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
executes_plan=false
executes_patch=false
```

It does not execute benchmark plans, apply patches, mutate repositories,
authorize automation, or authorize merge.
