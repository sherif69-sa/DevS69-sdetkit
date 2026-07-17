# Docs map and organization

Use this map when the `docs/` tree feels large. It separates the primary operator path from generated/sample artifacts, advanced programs, and historical material.

## Read in this order

| Step | Use this page | Why |
| --- | --- | --- |
| 1 | [Start here homepage](index.md) | Product homepage/router and canonical first path. |
| 2 | [Start Here in 5 Minutes](start-here-5-minutes.md) | Quick first run without browsing the whole tree. |
| 3 | [Operator essentials](operator-essentials.md) | Day-to-day runbook for first proof, failed CI triage, autopilot review, and guarded remediation review. |
| 4 | [Artifact reference and generated sample map](artifact-reference.md) | Runtime artifacts, workflow uploads, generated/sample labels, and artifact-to-action guidance. |
| 5 | [Investigation operator guide](investigation-operator-guide.md) | Diagnostic-only failure investigation with `sdetkit investigate`. |
| 6 | [Remediation cookbook](remediation-cookbook.md) | Human remediation playbooks after evidence identifies a failure class. |

## Information architecture

| Area | Primary docs | Notes |
| --- | --- | --- |
| Getting started | [Install](install.md), [Quickstart](quickstart-copy-paste.md), [Blank repo to value](blank-repo-to-value-60-seconds.md), [Ready to use](ready-to-use.md) | Keep these copy-pasteable and starter-oriented. |
| Operator guide | [Operator essentials](operator-essentials.md), [Local diagnostic queue operator guide](local-diagnostic-queue-operator-guide.md), [Operator onboarding](operator-onboarding-7-day.md), [Recommended CI flow](recommended-ci-flow.md) | Daily operator work belongs here, not in the README. |
| Investigation / diagnosis | [Investigation operator guide](investigation-operator-guide.md), [Adaptive Diagnosis Intelligence](adaptive-diagnosis.md), [First failure triage](first-failure-triage.md) | Diagnostic/report-only unless a guarded lane explicitly authorizes mutation. |
| Real-world adoption and learning | [Adopt in your repository](adoption.md), [Rust adoption-to-diagnosis proof](rust-adoption-to-diagnosis-proof.md), [CircleCI proof-command discovery](integrations/circleci-proof-discovery.md), [Artifact reference](artifact-reference.md), [Investigation operator guide](investigation-operator-guide.md) | Read-only external-repo evidence, complete ecosystem and provider proofs, learning observations, detector upgrades, and roadmap/radar control panels. |
| Product direction | [Product roadmap](roadmap/product-roadmap.md), [Current product delta](current-product-delta.md), [Platform capability matrix](contracts/platform-capability-matrix.v1.json) | Use the roadmap for execution order, the delta for released-versus-main truth, and the matrix for implemented capabilities, active gaps, external blockers, and denied authority. Keep all three secondary to the operator path. |
| Maintenance / autopilot | [Artifact reference](artifact-reference.md#maintenance-autopilot-upload-set), [Operations handbook](operations-handbook.md), [Automation bots](automation-bots.md) | Treat plans, candidates, and safe-fix outputs as evidence until reviewed policy approves the next step. |
| Quality gates | [Premium quality gate](premium-quality-gate.md), [Security gate](security-gate.md), [Determinism checklist](determinism-checklist.md), [Determinism contract](determinism-contract.md) | Gate docs explain proof and policy, not broad default auto-fix. |
| Artifact reference | [Artifact reference](artifact-reference.md), [CI artifact walkthrough](ci-artifact-walkthrough.md), [Evidence showcase](evidence-showcase.md) | Runtime artifacts live under `build/` and `.sdetkit/`; committed examples live under `docs/artifacts/`. |
| Contributor / developer docs | [Repo tour](repo-tour.md), [Contributing](contributing.md), [Release process](project/release-process.md), [Test bootstrap](test-bootstrap.md), [Project structure](project-structure.md) | Keep implementation and contribution material secondary to the operator path. |
| Generated/sample artifacts | [Artifact reference](artifact-reference.md), [Live-adoption product proof](live-adoption-product-proof.md) | Historical packs are preserved for traceability and are not the current runbook. |
| Historical archive | [Archive overview](archive/index.md), [Transition-era material map](archive/transition-era-material.md) | Non-primary; use only after the canonical path is working. |

## Directory guide

| Directory | Contents | Tidy rule |
| --- | --- | --- |
| `docs/` | Primary human docs and reference pages. | New primary guides must be linked from [Start here homepage](index.md) or this map. |
| `docs/artifacts/` | Committed generated/sample artifacts, proof packs, and historical completion material. | Label as generated/sample; do not treat as current runtime evidence. |
| `docs/archive/` | Historical and transition-era docs. | Keep non-primary material here when it is no longer part of the operator path. |
| `docs/business_execution/` | Business execution and GTM planning docs. | Keep business/program material out of first-run operator docs. |
| `docs/contracts/` | Formal contracts and schema-oriented references. | Link from the relevant feature doc and this map when the contract controls roadmap or operator decisions; do not duplicate contract text. |
| `docs/integrations/` | Integration packs and external workflow examples. | Keep platform-specific setup here. |
| `docs/kits/` | Kit-level packaging and capability docs. | Use after the core operator path is trusted. |
| `docs/project/` | Project-level architecture, workflow, release, quality, and enterprise docs. | Keep root copies as compatibility pointers only when checks or external links require them. |
| `docs/roadmap/` | Roadmap artifacts and reports. | Keep roadmap/reporting secondary to current operator guidance. |

## Navigation rules for future cleanup

## Real-world learning lanes

Use these pages when SDETKit is being evaluated as a repository doctor rather than only a local release gate:

| Lane | Primary pages | Operator rule |
| --- | --- | --- |
| Adoption surface | [Adopt in your repository](adoption.md), [Artifact reference](artifact-reference.md) | Detect repo shape and proof surfaces before recommending commands. |
| Rust end-to-end proof | [Rust adoption-to-diagnosis proof](rust-adoption-to-diagnosis-proof.md), [Doctor report contract](doctor-report-contract.md) | Carry explicit Rust repository evidence and saved Cargo failures into the shared review-first diagnosis contract. |
| CircleCI provider proof | [CircleCI proof-command discovery](integrations/circleci-proof-discovery.md), [Adopt in your repository](adoption.md) | Extract literal repository-owned `run` evidence while keeping orbs, parameters, dynamic configuration, and execution review-first. |
| Evidence and learning loop | [Investigation operator guide](investigation-operator-guide.md), [Adaptive Diagnosis Intelligence](adaptive-diagnosis.md) | Convert repeated gaps into detector/report/memory upgrades. |
| Roadmap control panels | [Product roadmap](roadmap/product-roadmap.md), [Current product delta](current-product-delta.md), [Platform capability matrix](contracts/platform-capability-matrix.v1.json), [Curated advanced docs material map](orphan-docs-material-map.md), [Artifact reference](artifact-reference.md) | Use the maintained roadmap and capability matrix to choose focused product slices; do not let generated trackers replace product direction. |

External repositories remain learning targets, not patch targets. Default posture is no install, no target tests, no mutation, no target PRs/issues, and no endorsement claim.


1. Keep the README as a concise front door; move command matrices to focused docs.
2. Keep [Operator essentials](operator-essentials.md) as the day-to-day runbook.
3. Keep [Artifact reference](artifact-reference.md) as the source of truth for runtime and uploaded artifact paths.
4. Do not move historical/generated artifact packs unless a separate migration map and link update are included.
5. Preserve the safety story everywhere: diagnostic/report-only by default; mutation only through explicit guarded policy and PR-only controls.

## Diagnostic intelligence

- [Cross-System Evidence Graph](evidence-graph.md)

## Evidence circuit review bundle

The completed evidence circuit documentation bundle consists of:

- [Evidence circuit architecture checkpoint](evidence-circuit-architecture-checkpoint.md)
- [Evidence graph summary](evidence-graph-summary.md)
- [Artifact reference and generated sample map](artifact-reference.md#evidence-circuit-artifact-source-map)
- [Operator evidence review guide](operator-evidence-review-guide.md)
- [Dashboard and reporting polish](dashboard-reporting-polish.md)
- [Evidence circuit review pack](evidence-circuit-review-pack.md)
- [Release-readiness evidence handoff](release-readiness-evidence-handoff.md)
