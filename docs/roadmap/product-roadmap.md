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

| Surface | Current truth after the active PR lands | Highest-value remaining gap |
| --- | --- | --- |
| Release | Repository candidate `1.1.0` has qualification and provenance paths. | Public package is still `1.0.3`; external publishing settings are unverified. |
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
| Jenkins and CircleCI discovery | Literal repository-owned command evidence preserves source context; dynamic behavior remains review-first. |
| Nested workspaces | Workspace path and working-directory identity are preserved across supported ecosystems. |
| Mixed-language monorepo operator vertical | Root and nested commands, workspace failure ownership, ambiguity, SafetyGate, ProtectedVerifier, Doctor, and observation-only RepoMemory are composed deterministically. |
| Review visibility | PR Quality, release handoff, post-merge verification, and exact-head merge readiness are implemented. |

## Selection rule

1. Red main, install, security, package, release, or required-check blocker.
2. Public 1.1.0 qualification and verification.
3. Stale product-control evidence that could cause duplicate or unsafe work.
4. Reviewed real-repository KPI evidence with explicit denominators.
5. Missing link in an active ecosystem or provider vertical.
6. Cross-report consistency and operator decision quality.
7. Human-approved bounded action contracts.
8. One narrowly proven mechanical automation family.
9. Packaging, documentation, UI, and public-release polish.

## Active executable PR ladder

| Order | Slice | Product value | Exit criteria |
| ---: | --- | --- | --- |
| 1 | **Release: qualify and publish 1.1.0** | Close the public package delta. | GitHub `pypi` environment, PyPI Trusted Publisher, frozen-SHA qualification, provenance, digest, and clean public install are proven. This remains **external configuration required**. |
| 2 | **Product evidence: collect reviewed real-repository product KPI evidence** | Replace anecdotal maturity claims with reviewed denominators. | Repeated observations produce source-backed diagnosis, proof-command, boundary, and actionability metrics. |
| 3 | **Provider depth: conservative Azure DevOps proof discovery** | Extend provider evidence without executing templates. | Literal repository-owned commands and source context are retained; templates, variables, matrices, service connections, and dynamic behavior remain review-first. |
| 4 | **Safety research: one narrow remediation promotion** | Evaluate a reversible PR-owned mechanical family. | Benchmark, independent verifier, rollback, trajectory, and zero unsafe false-authority decisions are proven before policy changes. |

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

### Phase 1 — Publish 1.1.0

Active blocker: [#1928](https://github.com/sherif69-sa/DevS69-sdetkit/issues/1928).

1. Freeze the exact candidate SHA.
2. Refresh external Python, JS/TS, and Go acceptance evidence.
3. Verify the protected GitHub `pypi` environment.
4. Verify the matching PyPI Trusted Publisher.
5. Create the signed tag only after those checks.
6. Retain qualification, distribution, provenance, and post-publication artifacts.
7. Verify `sdetkit==1.1.0` installs from public PyPI.
8. Update release references only after public verification.

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

Green CI alone is not a product release.

## Release horizons

- **1.1.0:** frozen public release-confidence and diagnosis foundation.
- **1.2.x:** reviewed KPI evidence, shared-contract audits, and evidence-backed provider depth such as Azure DevOps. C++ and mixed-monorepo operator proofs are already implemented.
- **1.3.x:** trusted report provenance, decision cards, and patch-proposal artifacts.
- **Later:** human-approved branch actions, one mechanical automation family, and a thin operator UI or GitHub App.

## Product KPIs

```text
public_release_delta
complete_ecosystem_vertical_count
complete_ci_provider_vertical_count
cpp_vertical_completion
multi_language_fixture_coverage
mixed_workspace_fixture_coverage
first_failure_extraction_rate
diagnosis_precision_rate
proof_command_actionability_rate
report_freshness_coverage
cross_report_consistency_rate
review_first_boundary_preservation_rate
unsafe_authority_rejection_rate
safe_fix_false_authority_count
operator_actionability_score
external_repo_proof_count
reviewed_trajectory_count
```

Targets:

- `safe_fix_false_authority_count = 0`;
- `review_first_boundary_preservation_rate = 100%` for unknown, security, dependency, release, workflow-permission, merge-conflict, and public-API changes;
- no public capability claim without a committed contract and fresh evidence;
- no KPI without a reviewed denominator and source provenance.

## Non-goals

No giant autonomous rewrite, premature cloud control plane, broad automatic patching, automatic dependency/security/release/merge actions, external repository mutation by default, replacement of established tools, or ecosystem/provider schema that bypasses shared contracts.

## Authority boundary

```text
automation_allowed=false
patch_application_allowed=false
security_dismissal_allowed=false
publication_authorized=false
merge_authorized=false
semantic_equivalence_proven=false
```
