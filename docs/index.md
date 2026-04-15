# Start here: deterministic release confidence

DevS69 SDETKit is a release-confidence CLI: it gives engineering teams deterministic ship/no-ship decisions with machine-readable evidence, using one repeatable command path from local to CI.

**Primary outcome:** know if a change is ready to ship.

**Canonical first path:** `python -m sdetkit gate fast` → `python -m sdetkit gate release` → `python -m sdetkit doctor`.

Need the fastest onboarding path? Start with [Start Here in 5 Minutes](start-here-5-minutes.md).

## What this is

SDETKit is a productized release-confidence path for engineering teams that need clear ship/no-ship decisions backed by structured artifacts.

Everything else is intentionally secondary until this canonical first-proof lane is trusted.

## How to use this docs site

Use the navigation in this order to reduce decision fatigue:

1. **Start Here (primary)** for first-run success on the canonical path.
2. **Team Rollout / CI (primary)** when moving from local proof to team adoption.
3. **Reference (secondary)** for command/options lookup and policy details.
4. **Advanced (secondary)** for maintainer, platform, and extension workflows.
5. **Archive / Historical (non-primary)** only when you need transition-era traceability.

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

### Fast start

Canonical first-proof commands (same as README and first-run guides):

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

1. [Install (canonical)](install.md)
2. [Start Here in 5 Minutes](start-here-5-minutes.md)
3. [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md)
4. [Release confidence explainer](release-confidence.md)

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
- Need fast troubleshooting: [First failure triage](first-failure-triage.md), [Adoption troubleshooting](adoption-troubleshooting.md), [Remediation cookbook](remediation-cookbook.md)
- Need compact navigation: [Docs map (compact)](docs-map.md)
- Need leadership packaging guidance: [CTO full-package review](cto-full-package-review.md)
- Need execution tracker input: `plans/top-tier-repo-execution-plan-2026-q2.json` (repo plan artifact)
- Need weekly control plane: [Top-tier program dashboard](top-tier-program-dashboard.md)
- Need package lane definitions: [Packaging lanes](packaging-lanes.md)
- Need governance policy table: [Policy compatibility matrix](policy-compatibility-matrix.md)
- Need operating support model: [Support and escalation model](support-and-escalation-model.md)
- Need multi-repo aggregation: [Portfolio reporting recipe](portfolio-reporting-recipe.md)
- Need leadership updates: [Executive weekly template](executive-weekly-template.md)
- Need KPI contract: [Top-tier KPI schema](kpi-schema.md)
- Need operator runbook: [Operations handbook](operations-handbook.md)
- Need rollout gates: [Pilot to rollout guide](pilot-to-rollout-guide.md)
- Need scale-phase assets: [P2 scale assets](p2-scale-assets.md)
- Need current references: [CLI reference](cli.md), [API](api.md), and [repo audit reference](repo-audit.md)
- Migrating older automation? Use [Legacy command migration map](legacy-command-migration-map.md)
- Need canonical-path health status? Use [Golden-path health signal](golden-path-health.md)
- Need drift enforcement? Run canonical path drift guard (`python scripts/check_canonical_path_drift.py --format json`)
- Need legacy usage inventory? Run legacy command analyzer (`python scripts/legacy_command_analyzer.py --format json`)
- Need one maturity number? Generate [Adoption scorecard](adoption-scorecard.md)
- Need guided canonical triage? Use [Operator onboarding wizard](operator-onboarding-wizard.md)
- Need API snapshot? Query serve observability endpoint (`GET /v1/observability`)
- Need docs IA guardrails? Use [Primary docs map](primary-docs-map.md)
- Need artifact contract inventory: [Artifact contract index](artifact-contract-index.json) (refresh with `python scripts/generate_artifact_contract_index.py`).
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

<div class="quick-jump" markdown>

[⚡ Fast start](#fast-start) · [🧭 Repo tour](repo-tour.md) · [🛠 CLI commands](cli.md) · [🩺 Doctor checks](doctor.md) · [🤝 Contribute](contributing.md) · [📦 Legacy reports](#legacy-reports)

</div>

## Legacy reports

### Top journeys

- Run first command in under 60 seconds
- Validate docs links and anchors before publishing
- Ship a first contribution with deterministic quality gates
