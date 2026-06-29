# Changelog

## Unreleased

This section describes capabilities merged to `main` after `1.0.3`. They are not claimed to be present in the published `sdetkit==1.0.3` wheel until a later release is built, verified, and published.

### Release confidence and diagnosis

- Add `sdetkit triage-ci` for advisory saved-log diagnosis with fixture coverage, structured failure classification, readable text and Markdown output, and first-failure operator guidance.
- Add deterministic FailureVector extraction, normalized failure contracts, first-real-failure reporting, affected-file hints, local reproduction guidance, and conservative risk classification.
- Add review-first SafetyGate decisions that preserve denied automation, patch, merge, security-dismissal, and semantic-equivalence authority.
- Add DiagnosticJob, diagnostic execution-plan handoff, worker-result, and trajectory provenance contracts.

### Verification and remediation safety

- Add isolated proof execution with copied workspaces, mutation detection, reserved-evidence protection, bounded proof profiles, timeout handling, and network-boundary assessment.
- Add protected verifier decisions, patch scoring, remediation-plan context, changed-file inventory checks, proof-requirement checks, and authority-boundary validation.
- Add replayable remediation benchmark scenarios, anti-cheat checks, control scorecards, and reviewed baseline regression gates.
- Preserve review-first handling for unknown, dependency, release, security, broad-scope, and verifier-sensitive failures.

### Trajectory, memory, and reporting

- Add trajectory storage, repository memory, failure-pattern insights, command provenance, proof-result retention, and deterministic reporting artifacts.
- Expand PR Quality reporting with exact-failure evidence, safety decisions, proof state, review handoffs, and denied-authority fields.
- Add trusted-main JUnit observation capture for retained test evidence.

### External adoption intelligence

- Add read-only repository surface discovery for Python, JavaScript/TypeScript, Go, Rust, Java, .NET, GitHub Actions, GitLab CI, Jenkins, security tools, release surfaces, and common evidence artifacts.
- Add adoption topology, proof recommendations, evidence bundles, external integration, learning-state, and public repository trial-matrix reports.
- Keep external adoption commands non-executing and non-mutating by default; recommended proof commands remain operator guidance.

### Quality, packaging, and governance

- Add Python 3.10 first-proof coverage and staged mypy ratchets for the diagnostic, trajectory, safety, adoption, and reporting boundaries.
- Align Ruff versions across project metadata, CI constraints, and pre-commit configuration.
- Add workflow-topology, required-check, public-surface, artifact-contract, release, security, and generated-artifact regression guards.
- Maintain SHA-pinned GitHub Actions, strict documentation builds, wheel-content validation, clean-wheel smoke installation, dependency review, SBOM, and vulnerability scanning lanes.

### Release qualification required

- Reconstruct and review the complete `1.0.3` to current-main product delta.
- Consolidate workflow and operator surfaces before release qualification.
- Prove the exact release-candidate artifacts on Python 3.10, 3.11, and 3.12.
- Refresh live-adoption proof at the release-candidate SHA.
- Migrate PyPI publication to reviewed Trusted Publishing configuration.

See [`docs/current-product-delta.md`](docs/current-product-delta.md) and [`docs/contracts/current-product-delta.v1.json`](docs/contracts/current-product-delta.v1.json).

## [1.0.3]

Released: 2026-04-18

- release stabilization: align package version, changelog, and release verification with v1.0.3.
- docs trust pass: replace enterprise contact placeholder and publish real content for key buyer-facing pages.
- artifacts hygiene: remove public placeholder values from the KPI dashboard seed artifact.

## [1.0.2]

Released: 2026-04-16

- Packaging: modernize license metadata.

## v1.0.1

Released: 2026-04-01
- CI gate: run `sdetkit doctor --all` and `sdetkit repo check --profile enterprise` on every PR.

## v1.0.0

Released: 2026-03-20
- Enterprise hardening: GitHub Actions pinned to commit SHAs.
- Dependency hygiene: requirements pinned and lockfiles added.
- Repo init/apply reliability: tolerate non-UTF-8 preset template files.
- Repo cleanliness: ignore local SDETKit workspace and docs build output.
- feat: add `name89-governance-scale-closeout` with strict closeout checks, pack emission, and execution evidence lane.
