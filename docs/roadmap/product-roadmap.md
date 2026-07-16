# Product roadmap

DevS69 SDETKit is an evidence-first release-confidence and repository-diagnosis layer for SDET, QA, DevOps, release, security, and platform teams.

It does not replace test runners, CI providers, security scanners, dependency tools, or release systems. It reads repository-owned evidence, connects signals, explains the first meaningful failure, recommends exact proof commands, and preserves review-first boundaries whenever action is not proven safe.

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
Which files, workspace, or workflow surface owns the failure?
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

## Current platform architecture

| Plane | Current responsibility | Implemented examples | Authority boundary |
| --- | --- | --- | --- |
| Evidence | Collect repository, CI, artifact, dependency, security, release, and exact-head evidence. | Gate artifacts, adoption surface, failure bundles, check intelligence, merge readiness. | Evidence does not authorize mutation. |
| Diagnosis | Extract and classify the first meaningful failure and identify owner surfaces. | FailureVector, ecosystem adapters, diagnostic vectors, current-head failure bundles. | Unknown or incomplete diagnosis remains review-first. |
| Safety | Decide eligibility and block unsafe categories or scope. | SafetyGate and policy matrix. | Eligibility is not patch authority. |
| Verification | Independently validate scope, proof, and anti-cheat boundaries. | ProtectedVerifier, protected proof chain, replayable benchmark scenarios. | Verification does not authorize merge or publication. |
| Reporting | Render exact status, evidence, uncertainty, and next human action. | Doctor, PR Quality, action reports, product maturity radar, merge readiness. | Predictions and recommendations are not proof. |
| Learning | Record reviewed action-response-diagnosis-proof outcomes. | TrajectoryStore, RepoMemory, history and pattern reports. | History informs review; it does not authorize the current change. |
| Orchestration | Run deterministic local jobs over file-backed artifacts. | Diagnostic queue runner and bounded local workers. | Local orchestration remains non-authorizing. |
| Adapters | Translate ecosystems and CI providers into shared contracts. | Python, JavaScript/TypeScript, Go, Rust, Java, .NET, GitHub Actions, GitLab CI, Jenkins. | Target repositories stay read-only by default. |

Hosted services, distributed queues, or managed dashboards are optional later deployment choices. They are not prerequisites for product value.

## Current implementation truth

| Capability | Current truth on `main` | Next improvement |
| --- | --- | --- |
| FailureVectorEngine | Implemented with shared extraction, classification, artifacts, and cross-ecosystem adapters. | Add evidence precision from more CI providers and mixed workspaces. |
| SafetyGate | Implemented with narrow mechanical eligibility and review-first blocked classes. | Promote no new category without reviewed trajectory, benchmark, and verifier proof. |
| TrajectoryStore and RepoMemory | Implemented with file-backed history, pattern, and reviewed learning surfaces. | Build reviewed real-repository denominators and usefulness KPIs. |
| ReplayableBenchmarkHarness | Implemented with repair evaluation contracts. | Grow scenarios from real adopter failures and mixed repositories. |
| ProtectedVerifier | Implemented with scope and anti-cheat checks. | Increase independence and evidence coverage before any remediation expansion. |
| PatchScorer and PR reporting | Implemented with diagnosis, safety, proof, and next-action output. | Improve portfolio-level usefulness evidence. |
| Local diagnostic queue | Implemented as deterministic file-backed orchestration. | Keep local; do not add hosted infrastructure without demand. |
| Merge readiness | Implemented for exact-head required-check state and next owner action. | Compose it into broader operator evidence portfolios where useful. |
| Ecosystem adoption | Complete review-first verticals exist across major language families. | Prove mixed-language monorepos and deepen provider coverage. |
| Public release | Repository metadata is `1.1.0`; public package remains `1.0.3`. | External configuration required for Trusted Publishing and public verification. |

The detailed release delta remains in [Current product delta](../current-product-delta.md).

## Roadmap decision: converge, release, then deepen adoption

The active roadmap has three parallel lanes:

1. **Repository truth convergence** — keep machine contracts and docs aligned with what is already implemented.
2. **Release qualification** — complete the frozen 1.1.0 publication only after protected external settings and exact public proof are verified.
3. **Post-candidate product expansion** — deepen provider and mixed-repository adoption without changing the frozen release candidate.

The release lane may be externally blocked while repository-owned, additive, review-first adoption work continues. No new feature may be smuggled into the frozen 1.1.0 candidate.

## Executable PR ladder

| Order | PR slice | Product value | Exit criteria |
| ---: | --- | --- | --- |
| 1 | **Roadmap: converge platform capability contracts** | Stops future sessions from repeating completed layers or following obsolete issue ladders. | Capability portfolio, checkpoint contracts, roadmap, and strict docs agree; authority remains false. |
| 2 | **Release: qualify and publish 1.1.0** | Closes the public package delta. | Protected GitHub `pypi` environment, matching PyPI Trusted Publisher, frozen-SHA artifact qualification, signed tag, provenance, digest verification, and clean public install are proven. This lane is `external configuration required`. |
| 3 | **Adoption: add CircleCI proof-command discovery** | Extends CI-provider evidence using the existing adoption contract. | Literal commands and source context are extracted; orbs, parameters, and dynamic configuration remain review-first; no target execution. |
| 4 | **Product proof: prove a mixed-language monorepo operator vertical** | Demonstrates workspace-specific discovery, failure ownership, and proof guidance in one realistic repository shape. | Each workspace keeps distinct commands, evidence, FailureVector ownership, Doctor/report output, and review-first boundaries. |
| 5 | **Metrics: publish reviewed real-repository product KPI evidence** | Replaces implementation-count vanity metrics with operator usefulness and diagnosis precision evidence. | Reviewed denominators, false-positive accounting, exact source provenance, and no prediction-as-proof claims. |
| 6 | **Adoption: add Azure DevOps proof-command discovery** | Adds another common enterprise CI surface after the provider contract is proven with CircleCI. | Literal script tasks are classified; templates, variables, and remote includes remain review-first. |
| 7 | **Safety: evaluate one narrow remediation policy promotion** | Tests whether one reversible mechanical pattern is mature enough for bounded assistance. | PR-owned scope, repeated clean trajectories, no-op/oracle/unsafe benchmark scenarios, ProtectedVerifier proof, exact rollback, and zero false authority. No broad auto-fix. |

Each slice must remain contributor-sized, independently reviewable, and separately proven. Completed components must be extended through their existing contracts rather than recreated under new names.

## Definition of a complete provider or ecosystem vertical

A vertical is product-ready only when the supported slice proves all applicable steps:

```text
language, workspace, package-manager, or CI-provider discovery
→ source-grounded proof-command recommendation
→ saved local or CI failure evidence
→ FailureVector class, tool, path, workspace, and uncertainty
→ SafetyGate decision and blocked authority
→ ProtectedVerifier or scope/proof integrity evidence where applicable
→ Doctor or PR Quality report integration
→ trajectory or reviewed-learning record
→ fixture-backed regression proof
→ operator documentation or sanitized public proof
```

A detector without actionable evidence is partial. A parser without discovery is partial. A report without exact source evidence is partial. A green result reached by weakened gates is invalid.

## Release horizons

### 1.1.0 — frozen release-confidence and diagnosis foundation

Goal: publish the current repository candidate with verified artifacts, provenance, and public installation.

Rules:

- no new language, provider, or remediation feature scope enters the candidate;
- configuration is not proof;
- the tag is not created or moved before frozen-SHA qualification;
- release and publication remain human-owned.

### 1.2.x — provider and mixed-repository depth

Goal: add CircleCI first, prove a mixed-language monorepo vertical, publish reviewed KPI evidence, then add Azure DevOps using the same shared contracts.

### Later — evidence-backed guarded remediation and enterprise deployment

Goal: promote only narrow, repeatedly proven mechanical patterns and add hosted deployment only when real adopters need it.

Potential later work:

- reviewed policy packs;
- additional CI-provider adapters such as Buildkite or CircleCI server variants;
- private registry and enterprise artifact guidance;
- independently operated verifier infrastructure;
- optional hosted reporting after local contracts and demand are proven.

## Product KPIs

The roadmap is measured by user trust and operator usefulness, not PR volume.

```text
public_release_delta
adoption_surface_detection_coverage
complete_ecosystem_vertical_count
complete_ci_provider_vertical_count
mixed_workspace_fixture_coverage
first_failure_extraction_rate
diagnosis_precision_rate
proof_command_actionability_rate
mean_time_to_primary_blocker
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
- `review_first_boundary_preservation_rate = 100%` for unknown, security, dependency, release, merge-conflict, and public-API changes;
- every new provider or ecosystem family has one complete vertical before another broad family begins;
- no public capability claim without a committed contract and fresh proof;
- no KPI without a reviewed denominator and source provenance.

## Selection rules for future PRs

Choose work in this order:

1. red-main, install, security, release, or required-check blockers;
2. stale roadmap or governance contracts that cause repeated or unsafe work;
3. external release qualification when the required human settings are available;
4. the missing link in the active provider or mixed-repository vertical;
5. real adopter or contributor pain with a clear proof contract;
6. reviewed KPI and learning evidence;
7. guarded remediation only when safety evidence supports promotion;
8. polish that improves adoption without delaying higher-value work.

Generated tracker noise, naming cleanup, dependency chores, and formatting changes remain valid only when they protect green main or strengthen product evidence.

## Non-goals

- a giant autonomous-agent rewrite;
- cloud queues or databases before local demand is proven;
- broad automatic patch application;
- automatic dependency upgrades;
- automatic security remediation or dismissal;
- automatic release publication;
- automatic merge authorization;
- replacing existing CI, test, scanner, or release tools;
- provider-specific schemas that bypass shared adoption, FailureVector, SafetyGate, verifier, reporter, or trajectory contracts.

## Authority boundary

The roadmap does not authorize automated patching, merging, publication, security dismissal, or semantic-equivalence claims.

```text
automation_allowed=false
patch_application_allowed=false
security_dismissal_allowed=false
publication_authorized=false
merge_authorized=false
semantic_equivalence_proven=false
```

Human review owns security acceptance, release publication, product direction, policy promotion, and business tradeoffs.
