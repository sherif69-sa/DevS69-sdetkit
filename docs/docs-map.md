# Docs map and organization

Use this map when the `docs/` tree feels large. It separates the primary operator path from generated/sample artifacts, advanced programs, and historical material.

## Read in this order

| Step | Use this page | Why |
| --- | --- | --- |
| 1 | [Documentation directory README](README.md) and [Start here homepage](index.md) | Directory landing page plus product homepage/router and canonical first path. |
| 2 | [Start Here in 5 Minutes](start-here-5-minutes.md) | Quick first run without browsing the whole tree. |
| 3 | [Operator essentials](operator-essentials.md) | Day-to-day runbook for first proof, failed CI triage, autopilot review, and guarded remediation review. |
| 4 | [Artifact reference and generated sample map](artifact-reference.md) | Runtime artifacts, workflow uploads, generated/sample labels, and artifact-to-action guidance. |
| 5 | [Investigation operator guide](investigation-operator-guide.md) | Diagnostic-only failure investigation with `sdetkit investigate`. |
| 6 | [Remediation cookbook](remediation-cookbook.md) | Human remediation playbooks after evidence identifies a failure class. |

## Information architecture

| Area | Primary docs | Notes |
| --- | --- | --- |
| Getting started | [Install](install.md), [Quickstart](quickstart-copy-paste.md), [Blank repo to value](blank-repo-to-value-60-seconds.md), [Ready to use](ready-to-use.md) | Keep these copy-pasteable and beginner-oriented. |
| Operator guide | [Operator essentials](operator-essentials.md), [Operator onboarding](operator-onboarding-7-day.md), [Recommended CI flow](recommended-ci-flow.md) | Daily operator work belongs here, not in the README. |
| Investigation / diagnosis | [Investigation operator guide](investigation-operator-guide.md), [Adaptive Diagnosis Intelligence](adaptive-diagnosis.md), [First failure triage](first-failure-triage.md) | Diagnostic/report-only unless a guarded lane explicitly authorizes mutation. |
| Maintenance / autopilot | [Artifact reference](artifact-reference.md#maintenance-autopilot-upload-set), [Operations handbook](operations-handbook.md), [Automation bots](automation-bots.md) | Treat plans, candidates, and safe-fix outputs as evidence until reviewed policy approves the next step. |
| Quality gates | [Premium quality gate](premium-quality-gate.md), [Security gate](security-gate.md), [Determinism checklist](determinism-checklist.md), [Determinism contract](determinism-contract.md) | Gate docs explain proof and policy, not broad default auto-fix. |
| Artifact reference | [Artifact reference](artifact-reference.md), [CI artifact walkthrough](ci-artifact-walkthrough.md), [Evidence showcase](evidence-showcase.md) | Runtime artifacts live under `build/` and `.sdetkit/`; committed examples live under `docs/artifacts/`. |
| Contributor / developer docs | [Repo tour](repo-tour.md), [Contributing](contributing.md), [Test bootstrap](test-bootstrap.md), [Project structure](project-structure.md) | Keep implementation and contribution material secondary to the operator path. |
| Generated/sample artifacts | [docs/artifacts/README.md](artifacts/README.md), [Live-adoption product proof](live-adoption-product-proof.md) | Historical packs are preserved for traceability and are not the current runbook. |
| Historical archive | [Archive overview](archive/index.md), [Transition-era material map](archive/transition-era-material.md) | Non-primary; use only after the canonical path is working. |

## Directory guide

| Directory | Contents | Tidy rule |
| --- | --- | --- |
| `docs/` | Primary human docs and reference pages. | New primary guides must be linked from [README.md](README.md), [index.md](index.md), or this map. |
| `docs/artifacts/` | Committed generated/sample artifacts, proof packs, and historical closeout material. | Label as generated/sample; do not treat as current runtime evidence. |
| `docs/archive/` | Historical and transition-era docs. | Keep non-primary material here when it is no longer part of the operator path. |
| `docs/business_execution/` | Business execution and GTM planning docs. | Keep business/program material out of first-run operator docs. |
| `docs/contracts/` | Formal contracts and schema-oriented references. | Link from the relevant feature doc instead of duplicating contract text. |
| `docs/integrations/` | Integration packs and external workflow examples. | Keep platform-specific setup here. |
| `docs/kits/` | Kit-level packaging and capability docs. | Use after the core operator path is trusted. |
| `docs/roadmap/` | Roadmap artifacts and reports. | Keep roadmap/reporting secondary to current operator guidance. |

## Navigation rules for future cleanup

1. Keep the README as a concise front door; move command matrices to focused docs.
2. Keep [Operator essentials](operator-essentials.md) as the day-to-day runbook.
3. Keep [Artifact reference](artifact-reference.md) as the source of truth for runtime and uploaded artifact paths.
4. Do not move historical/generated artifact packs unless a separate migration map and link update are included.
5. Preserve the safety story everywhere: diagnostic/report-only by default; mutation only through explicit guarded policy and PR-only controls.
