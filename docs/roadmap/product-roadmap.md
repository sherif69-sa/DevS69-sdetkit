# Product roadmap

DevS69 SDETKit is an evidence-first release-confidence and repository-diagnosis layer for SDET, QA, DevOps, release, security, and platform teams.

It does not replace test runners, CI providers, security scanners, dependency tools, or release systems. It reads their repository-owned evidence, connects the signals, explains the first meaningful failure, recommends exact proof commands, and preserves review-first boundaries when action is not proven safe.

## Product promise

For a repository an operator does not yet understand, SDETKit should answer:

```text
What kind of repository is this?
Which proof commands and artifact contracts does it already own?
What failed first, beneath wrapper noise?
Which files or workflow surfaces most likely own the failure?
What should a human run next?
Which actions are explicitly blocked?
What evidence should be retained for the next occurrence?
```

The product should be ambitious in understanding and conservative in action.

## Stable public first path

The public release-confidence path remains:

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

This path answers whether the current change is ready to ship and preserves machine-readable evidence.

After the stable path is working, the read-only repository-doctor expansion begins with:

```bash
python -m sdetkit adoption-surface \
  --root . \
  --out build/sdetkit/adoption-surface.json \
  --format report
```

The adoption artifact should lead into saved-log diagnosis, FailureVector evidence, Doctor or PR Quality reporting, and trajectory learning. Recommended commands remain advisory until an operator runs them in a trusted environment.

## End-to-end operator journey

```text
repository discovery
→ evidence-backed proof-command recommendations
→ saved local or CI failure evidence
→ FailureVector extraction and classification
→ SafetyGate and ProtectedVerifier review
→ Doctor and PR Quality reporting
→ trajectory and repo-memory learning
```

A product capability is not complete merely because a detector or parser exists. A complete vertical connects the operator journey from discovery to an actionable, review-first report.

## Product architecture

| Plane | Responsibility | Current product examples | Authority boundary |
| --- | --- | --- | --- |
| Evidence | Collect repository, CI, artifact, dependency, security, and release evidence. | Gate artifacts, adoption surface, failure bundles, manifests, provenance. | Evidence does not authorize mutation. |
| Diagnosis | Extract the first meaningful failure, classify it, identify affected surfaces, and recommend proof. | FailureVector, cross-ecosystem adapters, CI failure summaries, owner hints. | Unknown or incomplete diagnosis remains review-first. |
| Safety and verification | Evaluate scope and risk, protect proof integrity, and reject authority expansion or reward hacking. | SafetyGate, ProtectedVerifier, protected proof chain, benchmark rejection scenarios. | Patch, security-dismissal, merge, and semantic-equivalence authority remain false. |
| Reporting | Present exact decisions, evidence, uncertainty, and next human actions. | Doctor report bundles, PR Quality comments, JSON and Markdown artifacts. | Reported predictions and recommendations are not proof. |
| Learning | Record action, response, diagnosis, decision, proof, and outcome for future review. | TrajectoryStore, RepoMemory, benchmark and pattern reports. | Historical evidence informs review but does not authorize the current change. |
| Adapters | Translate language, package-manager, CI-provider, and security-tool evidence into shared contracts. | Python, JavaScript/TypeScript, Go, Java, GitHub Actions, and GitLab CI support. | Target repositories are read-only learning targets by default. |

Local deterministic contracts remain the default architecture. Hosted services, distributed queues, or managed dashboards are later deployment choices, not prerequisites for product value.

## Current implementation truth

| Surface | Current truth on `main` | Important gap |
| --- | --- | --- |
| Release confidence | Canonical gate and Doctor path is implemented with machine-readable artifacts. | Public package remains `1.0.3`; repository candidate is `1.1.0`. |
| Adoption discovery | Detects major language, package-manager, CI, security, docs, release, and artifact surfaces. | Provider and security depth is uneven across ecosystems. |
| CI provider discovery | GitHub Actions and GitLab CI have actionable evidence paths; Jenkins is detected. | Jenkins literal proof commands are not yet extracted. |
| Failure diagnosis | Python, JavaScript/TypeScript, Go, and Java saved-log adapters normalize into FailureVector evidence. | Rust `cargo test` and `cargo clippy` logs are not yet normalized. |
| Rust discovery | `Cargo.toml` produces Rust and Cargo detection with a review-first `cargo test` recommendation. | Explicit cargo-audit evidence is not yet reported, and the complete Rust vertical is not proven. |
| Safety | SafetyGate and ProtectedVerifier enforce reporting-only authority boundaries and anti-cheat checks. | Broad automatic patch application remains intentionally unavailable. |
| Reporting | Doctor and PR Quality expose structured status, evidence, manifests, and next actions. | More external-repository verticals need public proof through these existing contracts. |
| Learning | Trajectory, repo-memory, benchmark, and pattern surfaces exist. | Product KPIs need stronger evidence from repeated real-repository use. |

The detailed release delta remains in [Current product delta](../current-product-delta.md).

## Roadmap rule: release first, then expand vertically

The immediate product decision is:

1. keep `main` green and deterministic;
2. publish the maintained product roadmap;
3. qualify and publish the frozen 1.1.0 release without adding feature scope;
4. begin the post-1.1 adoption wave with one complete Rust vertical;
5. deepen CI-provider support through contributor-sized PRs;
6. expand guarded remediation only after repeated safety evidence exists.

This separates release completion from feature expansion and prevents the 1.1.0 candidate from becoming a moving target.

## Executable PR ladder

| Order | PR | Product value | Dependencies | Exit criteria |
| ---: | --- | --- | --- | --- |
| 1 | **Docs: publish the adoption-first product roadmap** ([#2014](https://github.com/sherif69-sa/DevS69-sdetkit/issues/2014)) | Gives maintainers and contributors one current product shape and an ordered execution plan. | Green `main`. | Roadmap and docs map are aligned; docs proof is green. |
| 2 | **Release: qualify 1.1.0 artifacts and Trusted Publishing** ([#1928](https://github.com/sherif69-sa/DevS69-sdetkit/issues/1928)) | Converts the mature repository candidate into an independently verified public release. | External GitHub `pypi` environment and PyPI Trusted Publisher verification. | Frozen SHA, exact-wheel qualification, public install verification, provenance, and post-release evidence. |
| 3 | **Diagnosis: add read-only Rust FailureVector adapters** ([#1937](https://github.com/sherif69-sa/DevS69-sdetkit/issues/1937)) | Extends saved-log diagnosis to `cargo test` and `cargo clippy` without executing target code. | 1.1.0 release completed or explicitly deferred without changing release scope. | Rust tool/class/path/exit-code evidence is fixture-tested; unknown output stays low-confidence and review-first. |
| 4 | **Adoption: detect explicit cargo-audit security evidence** ([#1946](https://github.com/sherif69-sa/DevS69-sdetkit/issues/1946)) | Makes Rust security posture discoverable from repository-owned evidence. | Existing adoption-surface contract. | cargo-audit is reported only when explicit evidence exists; no install, execution, dismissal, or remediation. |
| 5 | **Product proof: prove the Rust adoption-to-diagnosis vertical** ([#2045](https://github.com/sherif69-sa/DevS69-sdetkit/issues/2045)) | Demonstrates a complete external-repository journey through shared platform contracts. | #1937 and #1946. | Discovery, proof recommendation, saved-log FailureVector, Doctor/report evidence, safety boundaries, and public proof all pass together. |
| 6 | **CI integration: extract Jenkins proof commands from declarative pipelines** ([#1945](https://github.com/sherif69-sa/DevS69-sdetkit/issues/1945)) | Turns Jenkins detection into conservative, actionable operator guidance. | Independent contributor lane; does not block the Rust vertical. | Literal commands are classified with source context; dynamic Groovy remains review-first. |

Each PR must remain small enough to review and prove. Component PRs should not absorb the integration proof that belongs to the following vertical PR.

## Definition of a complete ecosystem vertical

An ecosystem is product-ready only when the supported slice proves all applicable steps:

```text
language and package-manager discovery
proof-command recommendation from repository evidence
CI-provider or local source context
saved failure-log normalization
FailureVector class, tool, paths, and uncertainty
SafetyGate / authority-boundary preservation
Doctor or PR Quality report integration
fixture-backed regression proof
operator documentation or sanitized public proof
```

A detected language without failure diagnosis is partial. A parser without adoption discovery is partial. A report without exact source evidence is partial.

## Release horizons

### 1.1.0 — release-confidence and diagnosis foundation

Goal: publish the current mature candidate with verified artifacts, provenance, and public installation.

No new language or provider feature scope should be added to the frozen candidate.

### 1.2.x — multi-ecosystem adoption verticals

Goal: prove Rust end to end, then improve CI-provider depth and mixed-repository behavior using the same shared contracts.

Primary work:

- Rust FailureVector adapters;
- explicit Rust security-surface discovery;
- Rust adoption-to-diagnosis proof;
- Jenkins proof-command extraction;
- mixed-repository fixture and confidence improvements driven by real gaps.

### Later — guarded remediation and enterprise integration

Goal: promote only narrow, repeatedly proven patterns into bounded remediation policies and add integration depth where real adopters require it.

Potential later work:

- reviewed policy packs;
- additional CI provider adapters;
- private registry and enterprise artifact guidance;
- higher-confidence safe candidates for formatting, import ordering, metadata alignment, or docs-link hygiene;
- optional hosted reporting after local contracts and demand are proven.

## Product KPIs

The roadmap is measured by user trust and operator usefulness, not PR volume.

```text
public_release_delta
adoption_surface_detection_coverage
complete_ecosystem_vertical_count
multi_language_fixture_coverage
first_failure_extraction_rate
diagnosis_precision_rate
proof_command_actionability_rate
mean_time_to_primary_blocker
review_first_boundary_preservation_rate
unsafe_authority_rejection_rate
safe_fix_false_authority_count
operator_actionability_score
external_repo_proof_count
open_source_contributor_time_to_first_proof
```

Initial operating targets:

- `safe_fix_false_authority_count = 0`;
- `review_first_boundary_preservation_rate = 100%` for unknown, security, dependency, release, and public-API changes;
- one complete external-repository vertical before adding another broad ecosystem family;
- no public capability claim without a committed contract and fresh proof.

## Selection rules for future PRs

Choose work in this order:

1. red-main, install, security, release, or required-check blockers;
2. release qualification needed to close the public product delta;
3. missing link in the active end-to-end ecosystem vertical;
4. real adopter or contributor pain with a clear proof contract;
5. provider or ecosystem depth that composes existing contracts;
6. guarded remediation only when safety evidence supports promotion;
7. polish that improves adoption without delaying higher-value work.

Generated tracker noise, stale reports, naming cleanup, and dependency chores remain valid only when they protect green main or strengthen product evidence.

## Non-goals for the next wave

- a giant autonomous-agent rewrite;
- cloud queues or databases before local contracts require them;
- broad automatic patch application;
- automatic dependency upgrades;
- automatic security remediation or dismissal;
- automatic release or publish actions;
- replacing existing CI, test, scanner, or release tools;
- separate ecosystem schemas that bypass shared FailureVector, adoption, Doctor, verifier, or trajectory contracts.

## Authority boundary

The roadmap does not authorize automated patching, merging, publication, security dismissal, or semantic-equivalence claims.

Unless a future independently verified policy explicitly changes the boundary, product artifacts must preserve:

```text
automation_allowed=false
patch_application_allowed=false
security_dismissal_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
```

Human review owns security acceptance, release publication, product direction, and business tradeoffs.
