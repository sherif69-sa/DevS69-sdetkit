# Start here: deterministic release confidence

DevS69 SDETKit is a release-confidence CLI for deterministic ship/no-ship decisions with machine-readable evidence.

**Primary outcome:** know if a change is ready to ship.

Canonical first path: `python -m sdetkit gate fast` -> `python -m sdetkit gate release` -> `python -m sdetkit doctor`.

Guided alias for first-time users: `python -m sdetkit start --journey fast-start --format markdown`.

This page is the product homepage/router for first-time adoption.

<div class="quick-jump" markdown>

[⚡ Fast start](#fast-start) · [🧭 Repo tour](repo-tour.md) · [🛠 CLI commands](cli.md) · [🩺 Doctor checks](doctor.md) · [🤝 Contribute](contributing.md) · [📦 Legacy reports](#legacy-reports)

</div>

### Top journeys

- Run first command in under 60 seconds
- Validate docs links and anchors before publishing
- Ship a first contribution with deterministic quality gates

## Fast start

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

New teams should stop here first, then inspect artifacts before exploring advanced commands.

## What you get

```text
build/gate-fast.json
build/release-preflight.json
```

## Try it quickly

- [Start Here in 5 Minutes](start-here-5-minutes.md)
- [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md)
- [First run quickstart](ready-to-use.md)
- [Quickstart (copy-paste)](quickstart-copy-paste.md)
- [Fit decision guide](decision-guide.md)

## Keep first adoption simple

1. Start with the canonical path (`gate fast` -> `gate release` -> `doctor`).
2. Optional guided onboarding prompt: `python -m sdetkit start --journey fast-start --format markdown`.
3. For reviewer handoff + adoption planning, prefer the one-command bundle:
   - `make adoption-control-loop-full`
4. Expand to individual sub-steps only when debugging or customizing:
   - `make gate-decision-summary`
   - `make adoption-followup`
   - `make adoption-followup-contract`
   - `make adoption-posture`
   - `make adoption-validate`

## Team rollout / CI

- [Adopt in your repository](adoption.md)
- [Team adoption checklist](team-adoption-checklist.md)
- [Operator essentials](operator-essentials.md)
- [Phase 1 execution checklist](phase1-execution-checklist.md)
- [Recommended CI flow](recommended-ci-flow.md)
- [CI artifact walkthrough](ci-artifact-walkthrough.md)
- [Release confidence flow](release-confidence-flow.md)
- [First failure triage](first-failure-triage.md)
- [Phase-by-phase execution plan](phase-by-phase-execution-plan.md)
- [One-by-one phase execution](phase-execution-one-by-one.md)

## Reference / advanced

- [CLI reference](cli.md)
- [Doctor checks](doctor.md)
- [Stability levels](stability-levels.md)
- [Versioning and support posture](versioning-and-support.md)
- [Integrations and extension boundary](integrations-and-extension-boundary.md)
- [Why SDETKit for teams](why-sdetkit-for-teams.md)
- [Use cases](use-cases.md)
- [Release confidence ROI](release-confidence-roi.md)
- [Repo health dashboard](repo-health-dashboard.md)
- [Business execution hub](business_execution/index.md)
- [Merge readiness and execution checklist](business_execution/08-merge-readiness-checklist.md)

## Legacy reports

Historical and transition-era references remain intentionally secondary to first-time adoption; use archive index material only after the canonical first proof path is operating.

- Archive index: [docs/archive/index.md](archive/index.md)
- Top-tier reporting troubleshooting: [top-tier-reporting-troubleshooting.md](top-tier-reporting-troubleshooting.md)

## Install and runtime notes

- Python 3.10+
- Prefer isolated environments
- `NO_MKDOCS_2_WARNING=1 python -m mkdocs build -q`
