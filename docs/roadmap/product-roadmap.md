# Product roadmap

DevS69 SDETKit is an evidence-first, local-first release-confidence and repository-diagnosis layer for SDET, QA, DevOps, release, security, and platform teams.

It does not replace test runners, CI providers, security scanners, dependency tools, build systems, or release systems. It reads repository-owned evidence, connects signals, explains the first meaningful failure, recommends exact proof commands, and preserves review-first boundaries whenever action is not proven safe.

Machine-readable portfolio:

- `docs/contracts/platform-capability-matrix.v1.json`

Supporting policy checkpoints:

- `docs/contracts/failure-vector-support-matrix.v1.json`
- `docs/contracts/safety-gate-policy-matrix.v1.json`

## Product promise

For a repository an operator does not yet understand, SDETKit should answer:

```text
What kind of repository is this?
Which proof commands and artifact contracts does it already own?
What failed first, beneath wrapper noise?
Which files, workspaces, or workflow surfaces most likely own the failure?
What should a human run next?
Which actions are explicitly blocked?
What evidence should be retained for the next occurrence?
```

The product is ambitious in understanding and conservative in action.

## Stable public first path

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

The adoption and diagnosis path builds on that stable surface:

```bash
python -m sdetkit adoption-surface \
  --root . \
  --out build/sdetkit/adoption-surface.json \
  --format report

python -m sdetkit product-maturity-radar \
  --root . \
  --out build/sdetkit/product-maturity-radar.json \
  --format text
```

Recommended target-repository commands remain advisory until an operator runs them in a trusted environment.

## End-to-end operator journey

```text
repository discovery
→ evidence-backed proof-command recommendations
→ saved local or CI failure evidence
→ FailureVector extraction and classification
→ SafetyGate review
→ ProtectedVerifier scope and proof checks
→ Doctor, PR Quality, and merge-readiness reporting
→ trajectory and RepoMemory learning
```

A product capability is not complete merely because a detector or parser exists. A complete vertical connects discovery to an actionable, review-first report through shared contracts.

## Current platform architecture

| Plane | Current responsibility | Implemented examples | Authority boundary |
| --- | --- | --- | --- |
| Evidence | Collect repository, CI, artifact, dependency, security, release, topology, and exact-head evidence. | Gate artifacts, adoption surface, workflow governance, failure bundles, manifests, provenance, merge readiness. | Evidence does not authorize mutation. |
| Diagnosis | Extract and classify the first meaningful failure and identify owner surfaces. | FailureVector, ecosystem adapters, CI failure summaries, current-head failure bundles. | Unknown or incomplete diagnosis remains review-first. |
| Safety | Decide eligibility and block unsafe categories or scope. | SafetyGate and policy matrix. | Eligibility is not patch authority. |
| Verification | Independently validate scope, proof, and anti-cheat boundaries. | ProtectedVerifier, protected proof chain, replayable benchmark scenarios. | Verification does not authorize merge or publication. |
| Reporting | Render exact status, evidence, uncertainty, and next human action. | Doctor, PR Quality, action reports, product maturity radar, workflow governance, merge readiness. | Predictions and recommendations are not proof. |
| Learning | Record reviewed action-response-diagnosis-proof outcomes. | TrajectoryStore, RepoMemory, history and pattern reports. | History informs review; it does not authorize the current change. |
| Orchestration | Run deterministic local jobs over file-backed artifacts. | Diagnostic queue runner and bounded local workers. | Local orchestration remains non-authorizing. |
| Adapters | Translate ecosystems, package managers, build systems, CI providers, and security tools into shared contracts. | Python, JavaScript/TypeScript, Go, Rust, Java, .NET, GitHub Actions, GitLab CI, Jenkins, CircleCI. | Target repositories stay read-only by default. |

Hosted services, distributed queues, or managed dashboards are optional later deployment choices. They are not prerequisites for product value.

## Current implementation truth

| Surface | Current truth on `main` | Highest-value remaining gap |
| --- | --- | --- |
| Release confidence | Canonical gate and Doctor paths produce machine-readable release evidence. | Public package remains `1.0.3`; repository candidate `1.1.0` is not publicly verified. |
| Adoption discovery | Root and nested workspaces are discovered across Python, JavaScript/TypeScript, Go, Rust, Java, and .NET from repository-owned evidence. | C++ is not yet represented as a first-class ecosystem. |
| CI-provider discovery | GitHub Actions and GitLab CI have actionable evidence paths; conservative Jenkins declarative `sh` and CircleCI literal `run` extraction are implemented. | Azure DevOps and other providers require evidence-backed, review-first adapters. |
| Failure diagnosis | Saved failures normalize into shared FailureVector evidence for Python, JavaScript/TypeScript, Go, Rust, Java, and .NET supported slices. | C++ compiler, linker, CTest, and common test-output adapters are absent. |
| Security evidence | Explicit cargo-audit, JavaScript package-audit, NuGet audit, Java dependency-check, GHAS, and repository security evidence can be reported conservatively. | Cross-ecosystem confidence and source-context rules need one shared consistency audit. |
| Safety and verification | SafetyGate, ProtectedVerifier, proof-chain integrity, isolation, scope checks, and anti-cheat rules exist. | Human-approved action execution needs an explicit authenticated decision and audit contract before implementation. |
| Reporting | Doctor, PR Quality, workflow-governance, maintenance, release-readiness, and exact-head merge-readiness surfaces exist. | Decision reports need consistent freshness, provenance, classification, and canonical next-action fields. |
| Learning | TrajectoryStore, RepoMemory, benchmark, and pattern surfaces exist. | Product KPIs need stronger repeated external-repository evidence. |
| Public command surface | The command inventory exists and compatibility is preserved. | Canonical operator journeys, tier explanations, and family-level help remain uneven. |
| Product UI | GitHub comments and artifacts provide the current operator surface. | A thin operator UI or GitHub App experience belongs after decision and action contracts stabilize. |

The detailed released-versus-main truth remains in [Current product delta](../current-product-delta.md).

## Completed execution chain

The roadmap must not reopen these accepted lanes unless current evidence proves regression:

| Completed lane | Evidence |
| --- | --- |
| Protected diagnosis and proof spine | FailureVectorEngine, SafetyGate, TrajectoryStore, RepoMemory, ReplayableBenchmarkHarness, ProtectedVerifier, PatchScorer, PRReporter, and local JobQueue contracts are connected. |
| Rust vertical | Rust saved-failure adapters, explicit cargo-audit discovery, and a complete adoption-to-diagnosis proof are complete. |
| Jenkins command discovery | Conservative literal declarative-pipeline shell-command extraction is complete; dynamic Groovy remains review-first. |
| CircleCI proof-command discovery | Literal repository-owned `run` commands preserve config, job, and optional step context; orbs, parameters, reusable commands, interpolation, multiline content, execution, and mutation remain review-first or blocked. |
| Nested workspace support | Python, JavaScript/TypeScript, Go, Rust, Java, and .NET workspace evidence is preserved with path and working-directory context. |
| Java vertical | Maven/Gradle discovery, saved failure evidence, OWASP Dependency-Check discovery, and end-to-end Doctor proof are complete. |
| .NET vertical | Project discovery, saved test normalization, NuGet audit evidence, and end-to-end Doctor proof are complete. |
| JavaScript package security | Explicit npm, pnpm, and Yarn audit commands are discovered without executing target code. |
| Review and merge visibility | Contributor-first PR Quality decisions, release handoff, post-merge verification, proof-profile visibility, and exact-head merge-readiness monitoring are implemented. |
| Report trust foundation | Workflow-governance freshness and deterministic provenance are implemented for the first major decision report. |

## Selection rule

Choose work in this order:

1. red main, install, security, release, package, or required-check blocker;
2. 1.1.0 release qualification and public verification;
3. stale product-control evidence that can cause duplicate or unsafe work;
4. the missing link in the active complete ecosystem or provider vertical;
5. cross-report consistency and operator decision quality;
6. real adopter or contributor pain with a clear proof contract;
7. human-approved bounded action contracts;
8. one narrowly proven mechanical automation family;
9. packaging, documentation, UI, and public-release polish.

Generated tracker noise, naming cleanup, dependency chores, and broad refactors are valid only when they protect green main or strengthen product evidence.

## Active executable PR ladder

| Order | PR slice | Product value | Exit criteria |
| ---: | --- | --- | --- |
| 1 | **Release: qualify and publish 1.1.0** | Closes the public package delta. | Protected GitHub `pypi` environment, matching PyPI Trusted Publisher, frozen-SHA qualification, provenance, digest verification, and clean public install are proven. This lane remains **external configuration required**. |
| 2 | **Adoption: build the complete C++ vertical** | Adds the next missing first-class ecosystem without reopening completed language lanes. | Four contributor-sized PRs cover discovery, saved-failure normalization, quality/security evidence, and complete operator proof. |
| 3 | **Product proof: prove a mixed-language monorepo operator vertical** | Demonstrates workspace-specific discovery, failure ownership, and proof guidance in one realistic mixed repository. | Fixture-backed discovery, owner context, saved failure, SafetyGate, ProtectedVerifier, and report output agree. |
| 4 | **Product evidence: collect reviewed real-repository product KPI evidence** | Replaces anecdotal maturity claims with reviewed denominators and source provenance. | Repeated adopter observations produce reviewable diagnosis, proof-command, boundary-preservation, and actionability metrics. |
| 5 | **Provider depth: add conservative Azure DevOps proof discovery** | Extends provider evidence without evaluating templates or executing target code. | Literal repository-owned commands and source context are preserved; variables, templates, service connections, and dynamic behavior remain review-first. |

The detailed phases below explain how these immediate slices compound into the final product. The ladder is a current execution contract, not permission to skip green-main or safety gates.

## Executable roadmap to final product release

### Phase 0 — Keep accepted main trustworthy

**Status:** operational and continuous.

Exit criteria for every PR:

```text
small_scope=true
current_head_verified=true
focused_proof=true
required_checks_green_or_explicitly_nonblocking=true
compatibility_preserved=true
rollback_known=true
protected_surfaces_not_weakened=true
```

### Phase 1 — Qualify and publish 1.1.0

**Active blocker:** [#1928](https://github.com/sherif69-sa/DevS69-sdetkit/issues/1928).

Repository code already represents version/tag alignment, build-once artifact reuse, Python 3.10/3.11/3.12 exact-wheel qualification, Trusted Publishing, package attestations, public-install verification, and GitHub-Release ordering.

Remaining proof is operational, not aspirational:

1. freeze and record the exact release-candidate SHA;
2. refresh external Python, JavaScript/TypeScript, and Go acceptance evidence against that SHA;
3. explicitly verify the protected GitHub `pypi` environment;
4. explicitly verify the matching PyPI Trusted Publisher binding;
5. create the signed `v1.1.0` tag only after those settings are verified;
6. retain qualification, distribution, provenance, and post-publication artifacts;
7. verify `sdetkit==1.1.0` installs from public PyPI;
8. update README release-channel references only after public verification;
9. record final public evidence in a post-release PR.

SDETKit must not silently create the release tag or publish the package.

### Phase 2 — Build the complete C++ vertical

**Epic:** [#2090](https://github.com/sherif69-sa/DevS69-sdetkit/issues/2090).

C++ must be delivered as four reviewable PRs.

#### 2A. C++ repository and proof-surface discovery

Detect repository-owned evidence from narrowly supported surfaces:

- `CMakeLists.txt`, `CMakePresets.json`, and CTest ownership;
- `meson.build` and Meson options;
- C++ source/header ownership without counting generated or vendored trees;
- literal configure, build, test, and analysis commands in supported CI or scripts;
- root and nested workspaces with preserved working-directory context.

Recommendations must be grounded in explicit evidence and remain manual.

#### 2B. Saved C++ failure normalization

Normalize supported saved evidence without invoking target tools:

- GCC, Clang, and fixture-backed MSVC compiler diagnostics;
- linker failures with conservative ownership hints;
- CTest and common GoogleTest/Catch2-style saved output;
- first meaningful failure, tool, class, paths, exit code, and explicit local repro command where known.

Unknown generators, proprietary build systems, and dynamic commands remain low-confidence and review-first.

#### 2C. C++ quality and security evidence

Detect only explicitly configured tools:

- `clang-tidy`;
- `cppcheck`;
- Clang/GCC sanitizers;
- CodeQL C/C++ workflow evidence;
- optional `clang-format` quality evidence;
- compile-database references when owned by the repository contract.

A generic C++ source tree must not imply those tools are installed or used.

#### 2D. Complete C++ operator proof

Prove one realistic fixture through:

```text
discovery
→ advisory commands
→ saved compiler or CTest failure
→ FailureVector
→ SafetyGate / ProtectedVerifier
→ Doctor or PR Quality
→ trajectory / RepoMemory evidence
```

Publish a sanitized operator page that distinguishes detected, inferred, proven, unsupported, and manual behavior.

### Phase 3 — Cross-ecosystem and provider consistency

Audit Python, JavaScript/TypeScript, Go, Rust, Java, .NET, C++, GitHub Actions, GitLab CI, Jenkins, and CircleCI shared behavior after the C++ vertical lands.

Required consistency dimensions:

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

Do not create ecosystem- or provider-specific schemas that bypass shared contracts. Add Azure DevOps or another provider only through a separate evidence-backed, conservative adapter PR.

### Phase 4 — Trust every decision report

Extend freshness and provenance from workflow governance to every report that can influence operator action.

Deliverables:

1. deterministic input digests;
2. generator and schema provenance;
3. exact-head or explicit snapshot binding;
4. missing, stale, malformed, and unavailable classifications;
5. cross-report consistency checks;
6. no authoritative zero from malformed or unavailable collection state;
7. one canonical next action per report.

### Phase 5 — Operator decision cards

Turn recommendations and alerts into reviewable decisions:

```text
current_valid
stale
duplicate
already_fixed
already_present
false_positive
insufficient_evidence
unsafe
unsupported
valuable_now
valuable_later
```

Human choices:

```text
accept
reject
defer
request_more_evidence
mark_duplicate
mark_already_done
prepare_patch_proposal
```

Every choice must record actor, target, exact head, reason, evidence, and timestamp.

### Phase 6 — Patch proposal artifacts without application

Generate bounded, reviewable patch proposals while preserving:

```text
patch_application_allowed=false
direct_main_mutation=false
merge_authorized=false
```

A proposal must include target files, expected diff shape, risk, rollback, focused proof, full proof, and verifier requirements.

### Phase 7 — Human-approved bounded execution

Enable execution only after an explicit policy PR proves:

```text
authenticated_operator=true
explicit_approval=true
exact_target=true
exact_scope=true
reason_required=true
dry_run_preview=true
rollback_required=true
audit_record_required=true
protected_verifier_required=true
direct_main_mutation=false
merge_authorized=false
automatic_dismissal_allowed=false
```

Initial capability should create or update a branch only. Human review continues to own merge and release decisions.

### Phase 8 — One narrow mechanical automation family

Promote only one repeatedly proven, reversible family, such as formatter-only output, deterministic metadata alignment, or docs-link hygiene.

Promotion requires fixture coverage, replay benchmarks, verifier independence, rollback, zero unsafe false-authority decisions, and a versioned policy.

Security, dependency, release, workflow-permission, public-API, and unknown failures remain excluded from the first automation family.

### Phase 9 — Productization and public command journeys

Deliver:

- stable installation and packaging;
- canonical CLI journeys and family-level help;
- versioned schemas and compatibility policy;
- deprecation and migration policy;
- docs site, quick start, operator guide, contributor guide, and known limitations;
- multi-language and multi-CI proof matrix;
- release rollback and support boundaries.

### Phase 10 — Security and supply-chain release readiness

Require:

```text
security_policy
threat_model
least_privilege_workflows
full_SHA_action_pins
dependency_review
trusted_publishing
SBOM
provenance
attestations
release_rollback
post_publish_verification
```

Security alerts may be explicitly dispositioned by an authenticated human with evidence and reason; silent or automatic dismissal remains forbidden.

### Phase 11 — Thin operator UI and GitHub App experience

Build UI only after report, decision, approval, and audit contracts stabilize.

The first UI should visualize existing contracts rather than invent a parallel control plane:

- repository and release posture;
- exact first failure;
- evidence freshness;
- decision cards;
- approved action preview;
- verifier result;
- trajectory history;
- rollback and audit record.

### Phase 12 — Public product release

The product is release-complete only when it has:

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

### 1.1.0 — public release-confidence and diagnosis foundation

Publish the frozen candidate with exact artifact qualification, provenance, Trusted Publishing, public installation proof, and post-release evidence. Do not add new ecosystem scope to the candidate.

### 1.2.x — ecosystem consistency, C++, and provider depth

Deliver C++ discovery and saved-failure adapters, complete the C++ vertical, audit shared contracts, and add only evidence-backed provider depth such as Azure DevOps.

### 1.3.x — trusted reports and human decision workflow

Extend report freshness/provenance, cross-report consistency, decision cards, and patch-proposal artifacts.

### Later — guarded action and operator product

Enable human-approved branch actions, one narrow mechanical automation family, stronger product packaging, and the thin operator UI or GitHub App surface.

## Product KPIs

Progress is measured by trust and operator usefulness, not PR volume:

```text
public_release_delta
complete_ecosystem_vertical_count
complete_ci_provider_vertical_count
cpp_vertical_completion
multi_language_fixture_coverage
mixed_workspace_fixture_coverage
adoption_surface_detection_coverage
first_failure_extraction_rate
diagnosis_precision_rate
proof_command_actionability_rate
mean_time_to_primary_blocker
report_freshness_coverage
cross_report_consistency_rate
review_first_boundary_preservation_rate
unsafe_authority_rejection_rate
safe_fix_false_authority_count
operator_actionability_score
external_repo_proof_count
reviewed_trajectory_count
open_source_contributor_time_to_first_proof
```

Initial operating targets:

- `safe_fix_false_authority_count = 0`;
- `review_first_boundary_preservation_rate = 100%` for unknown, security, dependency, release, workflow-permission, merge-conflict, and public-API changes;
- no new ecosystem family before the active vertical has complete proof or an explicit deferral decision;
- no public capability claim without a committed contract and fresh evidence;
- no KPI without a reviewed denominator and source provenance.

## Non-goals for the next wave

- a giant autonomous-agent rewrite;
- cloud queues or databases before local contracts require them;
- broad automatic patch application;
- automatic dependency upgrades;
- automatic security remediation or dismissal;
- automatic release, tag creation, publication, or merge;
- executing or mutating external target repositories by default;
- replacing existing CI, test, compiler, build, scanner, or release tools;
- ecosystem- or provider-specific schemas that bypass shared platform contracts.

## Authority boundary

The roadmap does not authorize automated patching, merging, publication, security dismissal, or semantic-equivalence claims.

Unless a future independently verified policy explicitly changes a narrow boundary, product artifacts must preserve:

```text
automation_allowed=false
patch_application_allowed=false
security_dismissal_allowed=false
publication_authorized=false
merge_authorized=false
semantic_equivalence_proven=false
```

Human review owns security acceptance, release publication, product direction, branch-action approval, and business tradeoffs.
