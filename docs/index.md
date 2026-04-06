# Start here: deterministic release confidence

DevS69 SDETKit gives engineering teams deterministic release go/no-go decisions with machine-readable evidence, using one repeatable command path from local to CI.

## What this is

SDETKit is a release-confidence command path for engineering teams that need clear ship/no-ship decisions backed by structured artifacts.

## Why trust it

- The core flow is explicit and repeatable: `gate fast` → `gate release` → `doctor`.
- Outputs are machine-readable JSON artifacts, not only terminal logs.
- Evidence examples in this repo use representative real output shapes (no fabricated customer claims or synthetic benchmarks).

## What to run first

1. [Install (canonical)](install.md)
2. [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md)
3. [Release confidence explainer](release-confidence.md)

If you want a guided run instead of the ultra-fast proof lane, use [First run quickstart](ready-to-use.md).

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
- Need contributor workflow: [Contributing](contributing.md)
- Need boundary guidance: [Stability levels](stability-levels.md) for adopters and contributors

## Secondary and advanced references

Deep references, advanced integrations, and historical material remain available in navigation and are intentionally secondary to first-time adoption.

If you need context after the canonical first-proof path is working:
- [SDETKit vs ad hoc tooling](sdetkit-vs-ad-hoc.md)
- [Repo cleanup plan](repo-cleanup-plan.md)
- [Repo health dashboard](repo-health-dashboard.md)
