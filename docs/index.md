# Start here: deterministic release confidence

<!-- product-proof-start -->
## Live-adoption product proof

The current package is backed by a committed live-adoption proof pack:

- **Proof page:** [Live-adoption product proof](live-adoption-product-proof.md)
- **Decision:** `SHIP with known STRICT_FINDINGS`
- **Blocking failures:** `0`
- **Known strict finding:** `legacy-noargs` compatibility behavior only
- **Validated strengths:** first-proof, core gates, review JSON/operator JSON, wheel smoke, fixture surfaces, and docs front-door commands.

<!-- product-proof-end -->

DevS69 SDETKit is a release-confidence CLI for deterministic ship/no-ship decisions with machine-readable evidence.

**Primary outcome:** know if a change is ready to ship.

Canonical first path: `python -m sdetkit gate fast` -> `python -m sdetkit gate release` -> `python -m sdetkit doctor`.

Guided alias for first-time users: `python -m sdetkit start --journey fast-start --format markdown`.

This page is the product homepage/router for first-time adoption.

<div class="quick-jump" markdown>

[⚡ Fast start](#fast-start) · [🧭 Choose your path](choose-your-path.md) · [🧭 Repo tour](repo-tour.md) · [🛠 CLI commands](cli.md) · [🩺 Doctor checks](doctor.md) · [📦 Artifact reference](artifact-reference.md) · [Operator guide](operator-essentials.md) · [🤝 Contribute](contributing.md) · [📦 Legacy reports](#legacy-reports)

</div>

### Top journeys


- Run a read-only external-repo adoption check and inspect evidence before prescribing work
- Convert repeated real-world repo gaps into detector, report, memory, or roadmap upgrades
- Use the product maturity radar as a roadmap control panel without replacing review-first governance
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

Compatibility aliases still supported: `python -m sdetkit gate fast`, `python -m sdetkit gate release`, and `python -m sdetkit doctor`.

## What you get

```text
build/gate-fast.json
build/release-preflight.json
```

## Pick your path first

- [Choose your path (30-second router)](choose-your-path.md)
- Equivalent namespace form: `python -m sdetkit release gate fast --format json --stable-json --out build/gate-fast.json`
- Full release path: `python -m sdetkit release gate fast` -> `python -m sdetkit release gate release` -> `python -m sdetkit release doctor`

## Try it quickly

- [Start Here in 5 Minutes](start-here-5-minutes.md)
- [Upgrade next commands (intent router)](upgrade-next-commands.md)
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

## Docs information architecture

Use this index as the primary human navigation map. The docs are organized around common operator jobs rather than historical delivery waves:

- **Getting started:** first commands, first artifacts, and adoption quickstarts.
- **Operator guide:** daily release-confidence commands and diagnostic-only investigation.
- **Investigation / diagnosis:** failure triage, adaptive diagnosis, and proof selection.
- **Maintenance / autopilot:** guarded workflow evidence, safe-fix audit trails, and PR-only remediation boundaries.
- **Quality gates:** release, security, premium, and determinism gates.
- **Artifact reference:** runtime artifact paths plus committed generated/sample artifact labels.
- **Contributor / developer docs:** repo tour, contribution flow, tests, and release maintenance.

For a compact tree-level map, use [Docs map and organization](docs-map.md).

## Team rollout / CI

## Real-world learning and governance

SDETKit can now run read-only adoption and learning lanes against cloned external repositories while keeping artifacts outside the target repo. These lanes are designed for product learning and operator evidence, not automatic target patching.

- Start with [Adopt in your repository](adoption.md) for external-repo readiness and adoption-surface evidence.
- Use [Artifact reference and generated sample map](artifact-reference.md) to understand machine-readable outputs and evidence bundles.
- Use [Artifact reference and generated sample map](artifact-reference.md#evidence-circuit-artifact-source-map) to map evidence-circuit docs to PR Quality, Runtime Proof, and ProtectedVerifier artifacts.
- Use [Investigation operator guide](investigation-operator-guide.md) when a CI log, repo shape, or proof command needs review-first diagnosis.
- Use this docs homepage and [Docs map and organization](docs-map.md) to keep radar, report, and governance tools connected to the broader roadmap.

Safety boundary: adoption and learning outputs are advisory unless an explicit guarded policy says otherwise.


- [Adopt in your repository](adoption.md)
- [Team adoption checklist](team-adoption-checklist.md)
- [Operator essentials](operator-essentials.md)
- [Investigation operator guide](investigation-operator-guide.md)
- [Artifact reference and generated sample map](artifact-reference.md)
- [Docs map and organization](docs-map.md)
- [Operator onboarding (7-day)](operator-onboarding-7-day.md)
- [Baseline readiness execution checklist](operations-execution-checklist.md)
- [Next 10 follow-ups](next-10-followups.md)
- [Recommended CI flow](recommended-ci-flow.md)
- [CI artifact walkthrough](ci-artifact-walkthrough.md)
- [Release confidence flow](release-confidence-flow.md)
- [First failure triage](first-failure-triage.md)
- [Phase-by-phase execution plan](operations-execution-plan.md)
- [One-by-one phase execution](operations-execution-guide.md)

## Investigation, maintenance, and quality gates

- [Adaptive Diagnosis Intelligence](adaptive-diagnosis.md)
- [Investigation operator guide](investigation-operator-guide.md)
- [Maintenance/autopilot artifact map](artifact-reference.md#maintenance-autopilot-upload-set)
- [Remediation cookbook](remediation-cookbook.md)
- [Premium quality gate](premium-quality-gate.md)
- [Security gate](security-gate.md)
- [PR automation for audit auto-fixes](pr-automation.md)

## Reference / advanced

- [CLI reference](cli.md)
- [Artifact reference and generated sample map](artifact-reference.md)
- [Doctor checks](doctor.md)
- [Stability levels](stability-levels.md)
- [Versioning and support posture](versioning-and-support.md)
- [Integrations and extension boundary](integrations-and-extension-boundary.md)
- [Why SDETKit for teams](why-sdetkit-for-teams.md)
- [Use cases](use-cases.md)
- [Release confidence ROI](release-confidence-roi.md)
- [Repo health dashboard](repo-health-dashboard.md)
- [Deep Repo Index Engine (Wave 1)](repo-index-engine.md)
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

## Architecture checkpoints

- [Evidence circuit architecture checkpoint](evidence-circuit-architecture-checkpoint.md): documents the completed FailureVectorEngine → SafetyGate → TrajectoryStore → RepoMemory → ProtectedVerifier → PR Quality → Runtime Proof → benchmark replay circuit and the reporting-only stop condition.
- [Operator evidence review guide](operator-evidence-review-guide.md): explains how reviewers should inspect the completed evidence circuit without granting patch, dismissal, merge, or semantic authority.
- [Evidence graph summary](evidence-graph-summary.md): maps the completed evidence circuit into reviewer-facing source, authority, and artifact inspection steps.
- [Dashboard and reporting polish](dashboard-reporting-polish.md): explains how to read PR Quality dashboards, artifact centers, Runtime Proof summaries, and ProtectedVerifier output without expanding authority.
- [Evidence circuit review pack](evidence-circuit-review-pack.md): bundles the dashboard, artifact, graph, operator, and release-readiness docs into one reviewer path.
- [Release-readiness evidence handoff](release-readiness-evidence-handoff.md): gives release reviewers a reporting-only template for PR Quality, Runtime Proof, and ProtectedVerifier evidence.
