# Artifact reference and generated sample map

Use this page when you need to understand where SDETKit writes evidence, which files are uploaded by CI, and which committed files are examples rather than live run outputs.

SDETKit's artifact story is intentionally evidence-first: gates, investigation, diagnosis, and maintenance lanes produce machine-readable files that humans can inspect before any remediation is considered.

## Safety baseline

Investigation, diagnosis, recommendation, planning, proof selection, classification, trending, candidate selection, probation, policy proposal, and dry-run outputs are diagnostic/report-only by default.

A file that says a fix is possible is not approval to mutate the repository. Mutation requires a separate reviewed policy path, explicit guarded flags, PR-only guardrails, and proof artifacts attached to the workflow run or pull request.

## Primary local artifacts

| Purpose | Path | Produced by | Notes |
| --- | --- | --- | --- |
| Release-readiness evidence package | `build/sdetkit/release-readiness-evidence/package.json`, `build/sdetkit/release-readiness-evidence/package.md` | `python -m sdetkit.release_readiness_evidence_package --root . --out-json build/sdetkit/release-readiness-evidence/package.json --out-md build/sdetkit/release-readiness-evidence/package.md --format text` | Reporting-only release evidence bundle; does not authorize publish or merge. |
| Fast release-confidence gate | `build/gate-fast.json` | `python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json` | First artifact to inspect. |
| Release preflight gate | `build/release-preflight.json` | `python -m sdetkit gate release --format json --out build/release-preflight.json` | Pairs with `gate-fast.json` for ship/no-ship decisions. |
| Doctor checks | `build/doctor.json` | `python -m sdetkit doctor --format json --out build/doctor.json` | Optional JSON form for machine-readable doctor output. |
| Adoption surface | `build/sdetkit/adoption-surface.json` | `python -m sdetkit adoption-surface --root . --out build/sdetkit/adoption-surface.json --format text` | Read-only repository surface map for languages, package managers, CI, security tools, artifact surfaces, and recommended proof commands. Does not run proof or authorize automation. |
| Failure investigation | `build/investigation/failure.json` | `python -m sdetkit investigate failure --log build/quality.log --format json --out build/investigation/failure.json` | Diagnostic-only triage result. |
| Repository investigation | `build/investigation/repo.json` | `python -m sdetkit investigate repo --root . --format json --out build/investigation/repo.json` | Diagnostic-only surface narrowing. |
| Adaptive diagnosis | `build/adaptive-diagnosis.json` | `PYTHONPATH=src python -m sdetkit.adaptive_diagnosis --log build/quality.log --format json --out build/adaptive-diagnosis.json` | Evidence-fitted diagnosis and proof commands. |
| Adaptive diagnosis learning | `.sdetkit/adaptive-diagnosis-memory.jsonl` | `python -m sdetkit adaptive learn record build/adaptive-diagnosis.json --db .sdetkit/adaptive-diagnosis-memory.jsonl` | JSONL learning events for matched signals, candidates, proof commands, recurrence, and operator outcome feedback. |
| Adaptive learning summary | operator-chosen JSON/stdout | `python -m sdetkit adaptive learn summarize --db .sdetkit/adaptive-diagnosis-memory.jsonl --format json` | Rollup of top recurring scenarios, weakest lanes, and promotion/exampletion calibration actions. |
| Operator brief | `build/sdetkit/operator-brief.md` | `python -m sdetkit adaptive brief --gate build/gate-fast.json --diagnosis build/adaptive-diagnosis.json --out build/sdetkit/operator-brief.md` | One-page handoff with gate result, diagnosis, candidates, first proof command, safe-fix decision, and owner action. |
| Operator PR comment | `build/sdetkit/operator-comment.md` | `python -m sdetkit adaptive brief --gate build/gate-fast.json --diagnosis build/adaptive-diagnosis.json --format comment --out build/sdetkit/operator-comment.md` | Compact PR-safe summary for green, safe mechanical, and review-first unknown flows. |

For schema-oriented contracts, see [`artifact-contract-index.json`](artifact-contract-index.json). That JSON index is the machine-readable contract inventory; this page is the human map.

## Maintenance autopilot upload set

The `maintenance-autopilot` workflow uploads these files when they are produced:

| Category | Paths | How to read them |
| --- | --- | --- |
| Autopilot report | `build/maintenance/autopilot/autopilot-report.json`, `build/maintenance/autopilot/autopilot-report.md` | Start here for the run summary. |
| Command-center plans | `build/maintenance/autopilot/command-center-dry-run-plan.json`, `build/maintenance/autopilot/command-center-live-plan.json` | Plans are audit evidence; they do not authorize mutation by themselves. |
| Core signals | `build/maintenance/autopilot/sdet_check.json`, `build/maintenance/autopilot/doctor.json`, `build/maintenance/autopilot/review.json`, `build/maintenance/autopilot/security-check.json` | Cross-check release, doctor, review, and security posture. |
| Investigation and diagnosis | `build/maintenance/autopilot/adaptive-diagnosis.json`, `build/maintenance/autopilot/adaptive-diagnosis.md`, `build/maintenance/autopilot/adaptive-diagnosis-error.json` | Diagnostic-only failure explanation and proof recommendations. |
| Safe-fix audit trail | `build/maintenance/autopilot/safe-fix-plan.json`, `build/maintenance/autopilot/adaptive-safe-remediation-result.json`, `build/maintenance/autopilot/adaptive-safe-remediation-result.md`, `build/maintenance/autopilot/adaptive-safe-remediation-error.json`, `build/maintenance/autopilot/adaptive-safe-commit-result.json` | Treat as guarded remediation evidence, not broad auto-fix permission. |
| Learning memory | `.sdetkit/maintenance/failure-memory.jsonl`, `.sdetkit/maintenance/adaptive-safe-fix-memory.jsonl`, `build/maintenance/autopilot/adaptive-safe-fix-learning-result.json`, `build/maintenance/autopilot/adaptive-safe-fix-learning-rollup.json`, `build/maintenance/autopilot/adaptive-safe-fix-learning-error.json` | Use to understand repeated patterns and remembered outcomes. |

The workflow keeps pull-request runs diagnostic by avoiding live remediation flags on `pull_request` events. Non-PR side effects are separately guarded in the workflow and should be reviewed with the uploaded artifacts.

## Committed generated and sample artifacts

`docs/artifacts/` is a committed evidence gallery. It contains generated/sample artifacts used for product proof, adoption examples, completion packs, and historical examplenstrations.

Labels to use when reading that tree:

- **Generated/sample material:** committed examples under `docs/artifacts/` are not produced by your local run unless a command explicitly writes there.
- **Canonical first-proof evidence:** current live-adoption proof packs are linked from the README and [`live-adoption-product-proof.md`](live-adoption-product-proof.md).
- **Historical completion report packs:** dated or numbered completion report folders are preserved for traceability and should not be treated as the current operator runbook.
- **Runtime artifacts:** files under `build/`, `.sdetkit/out/`, and `.sdetkit/maintenance/` are generated by local or CI commands and are the evidence to cite for a specific branch.

## Navigation from artifacts to action

Use this table before opening raw logs. It maps the most common artifact signals to the next safe operator action.

| If you see... | Open this artifact first | Next safe action | Mutation posture |
| --- | --- | --- | --- |
| A local release gate failed | `build/gate-fast.json` or `build/release-preflight.json` | Read `ok`, `failed_steps`, and the failing step output; then run `sdetkit investigate failure` on the captured log. | Diagnostic-only. |
| A CI log or PR check failed | `build/investigation/failure.json` | Read `classification`, `summary`, `next_actions`, `proof_commands`, `diagnostic_only`, `automation_allowed`, and `requires_human_review`. | Diagnostic-only. |
| The owning area is unclear | `build/investigation/repo.json` and the surface Markdown output | Use the repo/surface result to choose the smallest focused proof command. | Diagnostic-only. |
| You need to choose proof commands or rollout depth before running gates | `build/sdetkit/adoption-surface.json` | Review detected languages, package managers, CI, security tooling, artifact surfaces, and recommended proof commands; then choose the smallest proof path. | Read-only, non-authorizing. |
| A maintenance-autopilot run uploaded artifacts | `build/maintenance/autopilot/autopilot-report.md` and `build/maintenance/autopilot/adaptive-diagnosis.md` | Summarize the diagnosis and proof commands in the PR or issue before considering remediation. | Diagnostic-only on pull requests. |
| A safe-fix plan exists | `build/maintenance/autopilot/safe-fix-plan.json` | Review it as an audit plan; verify policy, branch, diff, and proof artifacts before any guarded lane runs. | Not approval to mutate. |
| A pattern keeps recurring | `.sdetkit/maintenance/failure-memory.jsonl` and `.sdetkit/maintenance/adaptive-safe-fix-memory.jsonl` | Use memory to explain recurrence and decide whether a policy proposal is warranted. | Evidence for review, not auto-approval. |
| You are reading committed samples | `docs/artifacts/` and [`live-adoption-product-proof.md`](live-adoption-product-proof.md) | Treat them as examples or historical proof packs; use runtime `build/` or `.sdetkit/` files for the current branch decision. | Not current-run evidence unless regenerated. |

Quick rules:

1. For ship/no-ship decisions, start with `build/gate-fast.json` and `build/release-preflight.json`.
2. For a failed command or CI log, run `sdetkit investigate failure` and read `diagnostic_only`, `automation_allowed`, `safe_to_auto_fix`, and `requires_human_review`.
3. For recurring maintenance failures, open the `maintenance-autopilot` upload and read the report, adaptive diagnosis, safe-fix plan, and learning memory together.
4. For human remediation steps, use [`remediation-cookbook.md`](remediation-cookbook.md) after the investigation or artifact summary points to a specific failure class.
5. For CI upload interpretation, use [`ci-artifact-walkthrough.md`](ci-artifact-walkthrough.md).

## Evidence circuit artifact source map

Use this source map when a PR or workflow run references the completed #1748
through #1761 evidence circuit. It connects the human docs to the artifact
surfaces that reviewers should inspect first.

| Review question | Open first | Then inspect | Authority posture |
| --- | --- | --- | --- |
| What is the completed evidence path? | [`evidence-graph-summary.md`](evidence-graph-summary.md) | [`evidence-circuit-architecture-checkpoint.md`](evidence-circuit-architecture-checkpoint.md) | Reporting-only source map |
| How should a reviewer read the evidence? | [`operator-evidence-review-guide.md`](operator-evidence-review-guide.md) | PR Quality, Runtime Proof, and ProtectedVerifier artifacts | Human review only |
| Which artifact explains PR-facing evidence? | PR Quality action report or review dashboard | [Dashboard and reporting polish](dashboard-reporting-polish.md), Runtime Proof summary, and ProtectedVerifier decision | Does not authorize merge |
| Which artifact explains runtime evidence? | `runtime-proof/summary/runtime-proof-artifacts.json` | `runtime-proof/summary/runtime-proof-artifacts.md` | Does not authorize patching or dismissal |
| Which artifact explains authority evidence? | PR Quality artifact manifest | authority evidence source map in the artifact center | Denied authority remains denied |
| Which artifact explains replay evidence? | benchmark replay report or Runtime Proof benchmark section | ProtectedVerifier benchmark replay evidence | Replay supports review, not approval |

### Evidence circuit reading order

1. Start with [Evidence graph summary](evidence-graph-summary.md) for the
   reviewer-facing source map.
2. Use [Operator evidence review guide](operator-evidence-review-guide.md) to
   decide which evidence source needs inspection.
3. Open PR Quality artifacts for the maintainer-facing summary.
4. Open Runtime Proof artifacts when runtime evidence or benchmark replay is
   referenced.
5. Open ProtectedVerifier output when authority boundaries are disputed.
6. Return to the PR only after confirming patch application, security
   dismissal, merge authorization, and semantic-equivalence claims remain
   denied.

This table is a navigation aid. It does not replace the proof command, PR
review, or release-readiness checklist.

## Evidence circuit review pack links

After using the evidence circuit artifact source map, continue with:

1. [Dashboard and reporting polish](dashboard-reporting-polish.md) for dashboard
   reading order.
2. [Evidence circuit review pack](evidence-circuit-review-pack.md) for the
   complete reviewer path.
3. [Release-readiness evidence handoff](release-readiness-evidence-handoff.md)
   when evidence must be summarized for release review.

These links are navigation aids only. They do not authorize patch automation,
security dismissal, merge, or semantic-equivalence claims.
