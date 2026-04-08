# Start here: deterministic release confidence

DevS69 SDETKit is a release-confidence CLI: it gives engineering teams deterministic ship/no-ship decisions with machine-readable evidence, using one repeatable command path from local to CI.

**Primary outcome:** know if a change is ready to ship.

**Canonical first path:** `python -m sdetkit gate fast` → `python -m sdetkit gate release` → `python -m sdetkit doctor`.

## What this is

SDETKit is a productized release-confidence path for engineering teams that need clear ship/no-ship decisions backed by structured artifacts.

Everything else is intentionally secondary until this canonical first-proof lane is trusted.

## Why trust it

- The core flow is explicit and repeatable: `python -m sdetkit gate fast` → `python -m sdetkit gate release` → `python -m sdetkit doctor`.
- Outputs are machine-readable JSON artifacts, not only terminal logs.
- Evidence examples in this repo use representative real output shapes (no fabricated customer claims or synthetic benchmarks).

```text
$ cd examples/adoption/real-repo
$ python -m sdetkit gate fast
exit 2  -> build/gate-fast.json: ok=false (fixture triage)
$ python -m sdetkit gate release
exit 2  -> build/release-preflight.json: ok=false (fixture triage)
$ python -m sdetkit doctor
exit 0  -> build/doctor.json: ok=true
```

Real fixture-oriented canonical flow; any failing gate result shown here is expected triage for the adoption fixture, not a product failure.

Context: [real-repo adoption fixture + golden artifacts](real-repo-adoption.md)

## What to run first

Canonical first-proof commands (same as README and first-run guides):

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

1. [Install (canonical)](install.md)
2. [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md)
3. [Release confidence explainer](release-confidence.md)

If you want a guided run instead of the ultra-fast proof lane, use [First run quickstart](ready-to-use.md).
For CLI-first orientation, run `python -m sdetkit --help` to see the same canonical path plus stability-tier grouping.
Need compatibility-lane expectations? See [Versioning and support posture](versioning-and-support.md#canonical-path-vs-compatibility-lanes-visibility-policy).

## What artifacts appear

Core first-run artifacts:

```text
build/
├── gate-fast.json
└── release-preflight.json
```

Inspect these keys first:
- `ok`
- `failed_steps`
- `profile`

For side-by-side behavior and deeper examples:
- [Before/after evidence example](before-after-evidence-example.md)
- [Evidence showcase](evidence-showcase.md)

## Decide fit quickly

Use [Decision guide](decision-guide.md) to confirm whether SDETKit is a good fit before broader rollout.

## Where to go next

- Need lane routing: [Choose your path](choose-your-path.md)
- Need team rollout: [Adopt in your repository](adoption.md)
- Need CI rollout: [Recommended CI flow](recommended-ci-flow.md)
- Need current references: [CLI reference](cli.md), [API](api.md), and [repo audit reference](repo-audit.md)
- Need contributor workflow: [Contributing](contributing.md)
- Need boundary guidance: [Stability levels](stability-levels.md) for adopters and contributors

## Secondary references (current)

This page is a product homepage/router, not a historical archive. Deep references and advanced material remain available and are intentionally secondary to first-time adoption.

If you need context after the canonical first-proof path is working:
- New contributor? Start with the safe-first lane in [Contributing](contributing.md#first-trustworthy-contribution-safe-first-lane).
- [SDETKit vs ad hoc tooling](sdetkit-vs-ad-hoc.md)
- [Repo cleanup plan](repo-cleanup-plan.md)
- [Repo health dashboard](repo-health-dashboard.md)

## Historical archive (non-primary)

Historical and transition-era documentation is preserved for traceability, but intentionally demoted in primary navigation.

- [Archive index](archive/index.md)
