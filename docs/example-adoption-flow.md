# Example adoption flow: from first run to release confidence

This is a **representative adoption walkthrough** for a team applying SDETKit to a repository with unknown readiness.

It is not presented as a public customer case study.

The commands below are real SDETKit commands, and this flow is meant to be practical for maintainers/operators.

## Scenario

You inherit a Python service repository that:

- has tests and linting, but no single release gate,
- has inconsistent local-vs-CI behavior,
- and no clear artifact trail when a gate fails.

You want to answer: **"Are we ready to ship, and if not, what should we fix first?"**

## Goals

1. Get a fast baseline confidence signal.
2. Run stricter release-oriented checks.
3. Produce machine-readable evidence artifacts.
4. Turn failures into a prioritized fix plan.
5. Roll the same flow into team CI.

## What do I run first?

Start in the target repository root:

```bash
python -m sdetkit gate fast
```

If you want an artifact immediately for triage and team sharing:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
```

### What this step tells you

- `ok: true` means your fast confidence profile currently passes.
- `ok: false` means SDETKit found at least one failing gate step.
- `failed_steps` tells you where to start remediation.

This is the right first gate because it is quick, deterministic, and gives a clear first backlog.

## What do I run for stricter release checks?

Run security budget enforcement and release preflight:

```bash
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0 --out build/security-enforce.json
python -m sdetkit gate release --format json --out build/release-preflight.json
```

### What this step tells you

- `security enforce` answers whether your current issue counts fit your policy budget.
- `gate release` answers whether stricter release preflight checks pass.
- These two checks establish a concrete go/no-go decision path.

## What output do I look at?

Focus on these artifacts first:

- `build/gate-fast.json`
  - `ok`
  - `failed_steps`
- `build/security-enforce.json`
  - `ok`
  - `counts`
  - `exceeded` / `exceeded_rules`
- `build/release-preflight.json`
  - `ok`
  - `failed_steps`

These fields give operators enough detail to route work without replaying full logs.

## What do I do when something fails?

Use this triage order:

1. **Fix the earliest failure with highest downstream impact** (often lint/test or baseline quality checks in `gate fast`).
2. **Re-run only the relevant command** (`gate fast`, then `security enforce`, then `gate release`).
3. **Capture artifact diffs** (`failed_steps`, `counts`, `exceeded_rules`) to confirm the fix moved the metric.
4. If policy failures are expected during onboarding, keep fast gate as required and phase strict budgets in after cleanup.

Use supporting playbooks when needed:

- [Adoption troubleshooting](adoption-troubleshooting.md)
- [Remediation cookbook](remediation-cookbook.md)

## Minimal rollout into team workflow (GitHub Actions)

Start with fast gate on PRs/pushes, then enforce strict path on release branches:

```yaml
name: sdetkit-progressive-gate

on:
  pull_request:
  push:
    branches: [main, release/**]

jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
      - name: Fast confidence gate
        run: python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
      - name: Strict release checks
        if: startsWith(github.ref, 'refs/heads/release/')
        run: |
          python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0 --out build/security-enforce.json
          python -m sdetkit gate release --format json --out build/release-preflight.json
```

Then upload the `build/*.json` files as CI artifacts so reviewers can triage quickly.

## Common mistakes

- Starting with strict budgets before establishing a passing fast gate baseline.
- Treating first-run failures as tool failure instead of integration backlog.
- Looking only at console logs and skipping JSON artifacts.
- Enforcing zero-tolerance security budgets too early when legacy issues are known.

## When to stop at the lightweight path (for now)

Stay on `gate fast` temporarily when:

- your repository is still in active cleanup,
- security counts are expected to violate strict thresholds,
- or teams are still standardizing local development baselines.

Promote to strict release gating once fast gate is consistently green and remediation velocity is stable.

## Caveat on this example

This page is intentionally **representative**.

It demonstrates a realistic operator workflow and command sequence, but does not claim a published third-party customer case.
