# Product roadmap

DevS69 SDETKit is an evidence-first, local-first release-confidence and repository-diagnosis layer for SDET, QA, DevOps, release, security, and platform teams. It reads repository-owned evidence, explains the first meaningful failure, recommends exact proof commands, and remains review-first whenever action is not proven safe.

Machine-readable authority:

- `docs/contracts/platform-capability-matrix.v1.json`
- `docs/contracts/failure-vector-support-matrix.v1.json`
- `docs/contracts/safety-gate-policy-matrix.v1.json`

## Product promise

```text
What kind of repository is this?
Which commands and artifact contracts does it own?
What failed first beneath wrapper noise?
Which workspace or workflow surface owns the failure?
What should a human run next?
Which actions are blocked?
What evidence should be retained?
```

SDETKit is ambitious in understanding and conservative in action. It does not replace CI, test runners, compilers, scanners, build systems, or release systems.

## Stable public path

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
python -m sdetkit adoption-surface --root . --out build/sdetkit/adoption-surface.json --format report
```

Target-repository commands remain advisory until a human runs them in a trusted environment.

## Shared operator journey

```text
repository discovery
→ workspace-scoped proof recommendations
→ saved failure evidence
→ FailureVector
→ SafetyGate
→ ProtectedVerifier
→ Doctor / PR Quality / merge readiness
→ trajectory / RepoMemory
```

A detector alone is not a complete product capability. A complete vertical must preserve shared evidence, diagnosis, safety, verification, reporting, and learning contracts.

## Current architecture

| Plane | Responsibility | Implemented examples | Boundary |
| --- | --- | --- | --- |
| Evidence | Collect repository, CI, artifact, security, release, topology, workspace, and exact-head evidence. | Gate artifacts, adoption surface, failure bundles, manifests, provenance. | Evidence does not authorize mutation. |
| Diagnosis | Extract the first meaningful failure and likely owner surface. | FailureVector, ecosystem adapters, C++ and workspace-owned saved failures. | Unknown diagnosis remains review-first. |
| Safety | Decide eligibility and block unsafe categories or scope. | SafetyGate and policy matrix. | Eligibility is not patch authority. |
| Verification | Validate scope, proof, and anti-cheat boundaries. | ProtectedVerifier, proof chain, replay benchmark. | Verification does not authorize merge. |
| Reporting | Render status, uncertainty, and one next human action. | Doctor, PR Quality, workflow governance, merge readiness. | Recommendations are not proof. |
| Learning | Retain reviewed outcomes. | TrajectoryStore and RepoMemory. | History does not authorize the current change. |
| Orchestration | Run deterministic local jobs over file-backed artifacts. | Diagnostic queue and bounded workers. | Orchestration remains non-authorizing. |
| Adapters | Translate ecosystems and providers into shared contracts. | Python, JS/TS, Go, Rust, Java, .NET, C++, GitHub Actions, GitLab, Jenkins, CircleCI. | Target repositories stay read-only by default. |

## Current implementation truth

| Surface | Current truth | Highest-value remaining gap |
| --- | --- | --- |
| Release | `sdetkit==1.2.0` is published from immutable tag `v1.2.0`, with provenance, matching public distribution digests, and a clean public install independently verified. | Keep future release verification exact-tag, fail-closed, and regression-guarded. |
| Ecosystems | Python, JS/TS, Go, Rust, Java, .NET, and C++ have supported evidence paths. | Continue shared-contract consistency audits. |
| Providers | GitHub Actions, GitLab, Jenkins literal shell, and CircleCI literal run evidence exist. | Azure DevOps needs a conservative adapter. |
| Mixed workspaces | A complete mixed-language monorepo operator vertical preserves root/nested commands, workspace ownership, ambiguity, Doctor, verifier, and memory evidence. | Reviewed real-repository product KPI evidence is next. |
| Safety | SafetyGate, ProtectedVerifier, isolation, scope, and anti-cheat checks exist. | Authenticated human decision and audit contracts must precede execution. |
| Reporting | Doctor, PR Quality, maintenance, release, governance, and exact-head merge readiness exist. | Freshness, provenance, classification, and canonical next-action consistency. |
| Learning | TrajectoryStore, RepoMemory, benchmark, and patterns exist. | Repeated reviewed external-repository denominators. |
| UI | GitHub comments and artifacts are the current operator surface. | Thin UI only after decision and audit contracts stabilize. |

Detailed released-versus-main truth: [Current product delta](../current-product-delta.md).

## Completed execution chain

| Completed lane | Evidence |
| --- | --- |
| Protected diagnosis spine | FailureVector, SafetyGate, TrajectoryStore, RepoMemory, benchmark, ProtectedVerifier, PatchScorer, PRReporter, and JobQueue are connected. |
| Rust, Java, and .NET verticals | Discovery, saved failures, security evidence, and end-to-end Doctor proof are implemented for supported slices. |
| C++ vertical | Discovery, compiler/linker/test normalization, explicit quality/security evidence, and complete operator proof are implemented. |
| Jenkins and CircleCI proof-command discovery | Literal repository-owned command evidence preserves source context; dynamic behavior remains review-first. |
| Nested workspaces | Workspace path and working-directory identity are preserved across supported ecosystems. |
| Mixed-language monorepo operator vertical | Root and nested commands, workspace failure ownership, ambiguity, SafetyGate, ProtectedVerifier, Doctor, and observation-only RepoMemory are composed deterministically. |
| Review visibility | PR Quality, release handoff, post-merge verification, and exact-head merge readiness are implemented. |
| Public 1.2.0 release | Exact wheel qualification, Trusted Publishing, provenance, public digest comparison, clean install, and GitHub Release evidence are complete. |

## Selection rule

1. Red main, install, security, package, release, or required-check blocker.
2. Stale product-control evidence that could cause duplicate or unsafe work.
3. Reviewed real-repository KPI evidence with explicit denominators.
4. Missing link in an active ecosystem or provider vertical.
5. Cross-report consistency and operator decision quality.
6. Human-approved bounded action contracts.
7. One narrowly proven mechanical automation family.
8. Packaging, documentation, UI, and future public-release polish.

## Active executable PR ladder

| Order | Slice | Product value | Exit criteria |
| ---: | --- | --- | --- |
| 1 | **Product evidence: collect reviewed real-repository product KPI evidence** | Replace anecdotal maturity claims with reviewed denominators. | Repeated observations produce source-backed diagnosis, proof-command, boundary, and actionability metrics. |
| 2 | **Provider depth: conservative Azure DevOps proof discovery** | Extend provider evidence without executing templates. | Literal repository-owned commands and source context are retained; templates, variables, matrices, service connections, and dynamic behavior remain review-first. |
| 3 | **Safety research: one narrow remediation promotion** | Evaluate a reversible PR-owned mechanical family. | Benchmark, independent verifier, rollback, trajectory, and zero unsafe false-authority decisions are proven before policy changes. |

## Executable roadmap

### Phase 0 — Keep `main` trustworthy

```text
small_scope=true
current_head_verified=true
focused_proof=true
required_checks_green_or_explicitly_nonblocking=true
compatibility_preserved=true
rollback_known=true
protected_surfaces_not_weakened=true
```

### Phase 1 — Maintain the verified public release path

The `v1.2.0` publication gate is complete.

1. Preserve the immutable tag and source-SHA record.
2. Keep the GitHub `pypi` environment and matching PyPI Trusted Publisher exact.
3. Build distributions once and retain manifest, qualification, and provenance artifacts.
4. Check out the exact tag before repository-owned post-publish verification scripts run.
5. Verify public filenames, SHA-256 digests, and clean installation before GitHub Release creation.
6. Update public references only after independent verification.
7. Treat changes after `v1.2.0` as unreleased until a later qualified publication.

SDETKit must not silently tag or publish.

### Phase 2 — Ecosystem consistency

C++, Rust, Java, .NET, and mixed-monorepo proofs are implemented for supported slices. Audit these shared dimensions without creating parallel schemas:

```text
workspace_identity
source_context
working_directory
proof_purpose
confidence
manual_or_auto_run_policy
executes_untrusted_code
failure_class
failure_tool
first_failure
owner_paths
security_evidence_source
authority_boundary
```

### Phase 3 — Reviewed product KPI evidence

Required reviewed metrics include discovery precision, first-failure extraction, workspace ownership precision, proof-command actionability, boundary preservation, unsafe-authority rejection, operator actionability, and explicit unavailable/malformed/unsupported denominators. No KPI may be published without source provenance and a reviewed denominator.

### Phase 4 — Provider depth

Add Azure DevOps only through a conservative adapter PR. Variables, templates, service connections, remote includes, matrices, and dynamic behavior remain unresolved and review-first.

### Phase 5 — Trust every decision report

Require deterministic input digests, generator/schema provenance, exact-head or snapshot binding, missing/stale/malformed/unavailable classifications, cross-report consistency, no authoritative zero from failed collection, and one canonical next action.

### Phase 6 — Operator decision cards

Classifications: `current_valid`, `stale`, `duplicate`, `already_fixed`, `already_present`, `false_positive`, `insufficient_evidence`, `unsafe`, `unsupported`, `valuable_now`, `valuable_later`.

Human choices: `accept`, `reject`, `defer`, `request_more_evidence`, `mark_duplicate`, `mark_already_done`, `prepare_patch_proposal`.

Every choice records actor, target, exact head, reason, evidence, and timestamp.

### Phase 7 — Patch proposals without application

```text
patch_application_allowed=false
direct_main_mutation=false
merge_authorized=false
```

A proposal includes target files, expected diff shape, risk, rollback, focused/full proof, and verifier requirements.

### Phase 8 — Human-approved bounded execution

Require authenticated operator, explicit approval, exact target/scope, reason, dry-run preview, rollback, audit record, ProtectedVerifier, no direct-main mutation, no merge authority, and no automatic dismissal. Initial execution may create or update a branch only.

### Phase 9 — One mechanical automation family

Promote only a repeatedly proven reversible family such as formatter-only output, deterministic metadata alignment, or docs-link hygiene. Security, dependency, release, workflow-permission, public-API, and unknown failures remain excluded.

### Phase 10 — Productization

Deliver stable installation, canonical CLI journeys, versioned schemas, compatibility/deprecation policy, docs, support boundaries, multi-language/multi-CI proof, and rollback guidance.

### Phase 11 — Supply chain and thin UI

Require security policy, threat model, least privilege, full-SHA pins, dependency review, Trusted Publishing, SBOM, provenance, attestations, rollback, and post-publication verification. UI must visualize existing contracts rather than create a parallel control plane.

### Phase 12 — Public product release

```text
stable_package=true
canonical_journeys=true
versioned_schemas=true
compatibility_policy=true
security_and_support_docs=true
trusted_release_pipeline=true
multi_ecosystem_proof=true
human_decision_UX=true
bounded_action_contract=true
known_limitations=true
external_adoption_evidence=true
```
