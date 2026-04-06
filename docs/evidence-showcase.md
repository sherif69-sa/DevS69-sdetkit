# Evidence showcase: representative artifacts from this repository

Use this page to see real output shapes from a representative SDETKit run in this repository.

For first-time adoption, start with [Start here](index.md), [Install](install.md), and [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md).

Canonical artifact interpretation is in [CI artifact walkthrough](ci-artifact-walkthrough.md).

## Representative scenario

Scenario used for this evidence set:

- Operator runs a fast quality gate, strict security budget enforcement, then release preflight.
- The run intentionally produces actionable failures to show triage behavior.

Commands actually run:

```bash
mkdir -p build
python -m sdetkit gate fast --format json --out build/gate-fast.json
python -m sdetkit security enforce --format json --out build/security-enforce.json --max-error 0 --max-warn 0 --max-info 0
python -m sdetkit gate release --format json --out build/release-preflight.json
```

Observed exit codes in this run:

- `gate fast`: `2`
- `security enforce`: `1`
- `gate release`: `2`

## Artifact files produced

```text
build/
├── gate-fast.json
├── security-enforce.json
└── release-preflight.json
```

## What each artifact means

### `build/gate-fast.json`

Purpose:

- Structured result of the fast confidence lane.
- Shows which sub-steps passed/failed (`doctor`, `ci_templates`, `ruff`, `ruff_format`, `mypy`, targeted `pytest`).

Real excerpt from this run:

```json
{
  "failed_steps": [
    "ruff",
    "ruff_format"
  ],
  "ok": false,
  "profile": "fast"
}
```

Operator value:

- Deterministic failed step IDs without scanning long logs.
- Direct handoff to remediation lanes.

### `build/security-enforce.json`

Purpose:

- Security budget decision object with explicit counts, limits, and exceeded metrics.

Real excerpt from this run:

```json
{
  "counts": {
    "error": 0,
    "info": 131,
    "total": 131,
    "warn": 0
  },
  "exceeded": [
    {
      "count": 131,
      "limit": 0,
      "metric": "info"
    }
  ],
  "ok": false
}
```

Operator value:

- Gate reason is machine-readable (`info` budget exceeded), so policy decisions are auditable.

### `build/release-preflight.json`

Purpose:

- Release lane aggregation that records preflight step outcomes.
- Shows whether `doctor --release`, playbook validation, and nested `gate fast` passed.

Real excerpt from this run:

```json
{
  "failed_steps": [
    "gate_fast"
  ],
  "ok": false,
  "profile": "release"
}
```

Operator value:

- Explains why release preflight failed without replaying the full workflow manually.

## What to inspect first when a gate fails

1. Open `build/release-preflight.json` for the top-level release decision.
2. If `gate_fast` failed, inspect `build/gate-fast.json` and read `failed_steps`.
3. For policy/budget failures, inspect `build/security-enforce.json` (`counts`, `limits`, `exceeded`).
4. Use raw logs only after artifact-level triage.

## How teams can reference these artifacts in PRs/releases

- Upload JSON files as CI artifacts.
- In PR summaries, cite `ok`, `failed_steps`, and any exceeded security metric.
- Keep the artifact links with release notes so decision inputs remain auditable.

## Why this is better than raw terminal logs alone

- JSON artifacts preserve structure (`ok`, `failed_steps`, `counts`, `limits`) for automation.
- They are easier to diff between runs than free-form logs.
- Reviewers confirm decision inputs quickly instead of parsing mixed stdout/stderr.

## Limitations / representative-example note

- This is a representative run from this repository state and branch, not a universal baseline for all repositories.
- Counts and failing step IDs vary by project content, policy thresholds, and tooling state.
- Snippets here come from actual generated outputs in this run (no fabricated artifacts).

## Related pages

- Behavior comparison: [Before/after evidence example](before-after-evidence-example.md)
- Product model: [Release confidence](release-confidence.md)
- Fit decision: [Decision guide](decision-guide.md)
