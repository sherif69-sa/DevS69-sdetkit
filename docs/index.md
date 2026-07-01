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

**From noisy CI evidence to a reviewable decision, diagnosis, and exact next command.**

**Primary outcome:** know if a change is ready to ship.

Canonical first path: `python -m sdetkit gate fast` -> `python -m sdetkit gate release` -> `python -m sdetkit doctor`.

This page is the product homepage/router for first-time adoption.

<div class="quick-jump" markdown>

[⚡ Fast start](#fast-start) · [🧭 Repo tour](repo-tour.md) · [🛠 CLI commands](cli.md) · [🩺 Doctor checks](doctor.md) · [🤝 Contribute](contributing.md) · [📦 Legacy reports](#legacy-reports)

</div>

### Top journeys

- Run first command in under 60 seconds
- Validate docs links and anchors before publishing
- Ship a first contribution with deterministic quality gates

## Why teams use SDETKit

- **Release owners:** deterministic `SHIP` / `NO-SHIP` evidence.
- **SDET and QA engineers:** the first meaningful failure rather than a wrapper verdict.
- **Platform teams:** machine-readable evidence and exact proof commands.
- **Reviewers:** explicit review-first authority boundaries.

## Failure to next action

```text
classification: test
first_failure: FAILED tests/test_release_contract.py::test_wheel_smoke
affected_file: tests/test_release_contract.py
verification: python -m pytest -q tests/test_release_contract.py -o addopts=
decision: review-first
```

Use [First failure triage](first-failure-triage.md) for the shortest operator path and [Investigation operator guide](investigation-operator-guide.md) for the full safety contract.

## Public launch proof

The [public launch proof](public-launch-proof.md) shows a realistic saved pytest failure reduced to its first failing node, owning file, focused proof command, and review-first decision. It also profiles a fixture-based Python, JavaScript/TypeScript, and Go repository without dependency installation, target-code execution, target mutation, or merge authorization.

The artifacts are reproducible, tied to an immutable source SHA, accessible as text, and marked **main-only until the qualified 1.1.0 release**.

## Fast start

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

Generated artifacts:

```text
build/gate-fast.json
build/release-preflight.json
```

New teams should stop here first, inspect the evidence, and only then expand into advanced lanes.

## Choose your path

- [Choose your path](choose-your-path.md)
- [Start Here in 5 Minutes](start-here-5-minutes.md)
- [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md)
- [First run quickstart](ready-to-use.md)
- [Fit decision guide](decision-guide.md)

## Operator path

- [Operator essentials](operator-essentials.md)
- [Investigation operator guide](investigation-operator-guide.md)
- [First failure triage](first-failure-triage.md)
- [Public launch proof](public-launch-proof.md)
- [Adaptive Diagnosis Intelligence](adaptive-diagnosis.md)
- [Artifact reference and generated sample map](artifact-reference.md)
- [CI artifact walkthrough](ci-artifact-walkthrough.md)
- [Recommended CI flow](recommended-ci-flow.md)
- [Release confidence flow](release-confidence-flow.md)

Safety boundary: adoption and learning outputs are advisory unless an explicit guarded policy says otherwise.

## Adoption and team rollout

- [Adopt in your repository](adoption.md)
- [Team adoption checklist](team-adoption-checklist.md)
- [Operator onboarding (7-day)](operator-onboarding-7-day.md)
- [Real repository adoption](real-repo-adoption.md)
- [Portfolio readiness](portfolio-readiness.md)
- [Portfolio reporting recipe](portfolio-reporting-recipe.md)

SDETKit can inspect cloned external repositories in read-only mode, keep artifacts outside the target repository, and report unknown surfaces as review-first.

## Quality, security, and remediation

- [Premium quality gate](premium-quality-gate.md)
- [Security gate](security-gate.md)
- [Remediation cookbook](remediation-cookbook.md)
- [PR automation boundary](pr-automation.md)
- [Versioning and support posture](versioning-and-support.md)
- [Stability levels](stability-levels.md)

## Contributor and developer path

- [Contributing](contributing.md)
- [Repository tour](repo-tour.md)
- [CLI reference](cli.md)
- [Docs map and organization](docs-map.md)
- [Project structure](project-structure.md)
- [Operations handbook](operations-handbook.md)
- [Release process](project/release-process.md)

## Architecture and evidence

- [Evidence circuit architecture checkpoint](evidence-circuit-architecture-checkpoint.md)
- [Operator evidence review guide](operator-evidence-review-guide.md)
- [Evidence graph summary](evidence-graph-summary.md)
- [Evidence circuit review pack](evidence-circuit-review-pack.md)
- [Release-readiness evidence handoff](release-readiness-evidence-handoff.md)

## Legacy reports

Historical and transition-era references remain intentionally secondary to first-time adoption. Use the [archive index](archive/index.md) only after the canonical first proof path is operating.

- [Top-tier reporting troubleshooting](top-tier-reporting-troubleshooting.md)

## Install and runtime notes

- Python 3.10+
- Prefer isolated environments.
- Validate docs with `NO_MKDOCS_2_WARNING=1 python -m mkdocs build -q`.
