# Changelog

## Unreleased

- `gate fast` now works in any repository: it runs the repository's own test suite and only runs ruff/mypy when the repository configures them, recording skipped steps with reasons. SDETKit's own conventions (fixed smoke-test files, repo-layout scripts, CI template validation) are opt-in through `[tool.sdetkit.gate]`.
- `doctor --release` only requires a release workflow and tag-check script when the repository declares `[tool.sdetkit.doctor] release_tag_check_script`.
- Gate next-action cards reuse the diagnosis of failing JSON sub-steps (doctor, nested gates) instead of dumping their raw output, and `gate release` diagnoses step output before stripping it.
- `mission-control run` reports `NOT_RUN` (never `SHIP`) when no checks were executed, and leads its next actions with `--execute`.
- Importing `sdetkit` no longer patches Python itself (`builtins.__build_class__`, `argparse.ArgumentParser`, `Path.write_text`/`write_bytes`).
- Fixed stdlib-shadowing detection for packages and `repo init` template copying, both of which looked for `init_.py` instead of `__init__.py`.
- `trust-assets --execute` runs its commands in the target `--root`, and the roadmap manifest resolves the repository from the working directory instead of the installed package location; both previously wrote into the wrong repository.
- `maintenance --fix` runs each pre-commit hygiene hook separately (`pre-commit run` takes one hook id), so the action can succeed.
- The test suite now fails if any test modifies a tracked repository file.
- mypy now type-checks the release-confidence decision path (`gate`, `gate_config`, `doctor`, `repo`, `investigate`, `mission_control`, `security_gate`, `adaptive_diagnosis`, `evidence`); previously it was suppressed for these modules.
- The required `maintenance-autopilot` context now comes from the real maintenance-autopilot job; the legacy status bridge no longer posts a hard-coded `success` for it.
- `security scan` no longer reports readable `name=WORD` literals (for example `latest_decision=NOT_RUN`) as high-entropy secrets; values containing digits are still checked.
- Failure extraction recognises pytest collection errors and no longer classifies a `FAILED` pytest node as lint because the log mentions ruff.

## [1.2.0]

Released: 2026-07-18

- Added exact first-failure extraction, shared FailureVector evidence, review-first SafetyGate decisions, protected verification, trajectory records, and repository memory.
- Added deterministic release-readiness, merge-readiness, PR Quality, workflow-governance, package, provenance, and operator-reporting contracts.
- Added read-only adoption and saved-failure diagnosis across Python, JavaScript/TypeScript, Go, Rust, Java, .NET, and C++ repositories.
- Added conservative CI-provider evidence for GitHub Actions, GitLab CI, Jenkins, and CircleCI.
- Added complete fixture-backed C++ and mixed-language monorepo adoption-to-diagnosis operator proofs.
- Added multi-workspace ownership, quality/security evidence, anti-cheat boundaries, and review-first unknown handling.
- Updated dependency, documentation, security, packaging, exact-wheel qualification, and release supply-chain gates.
- Published through PyPI Trusted Publishing from immutable tag `v1.2.0` at source commit `5165a82f8cd2ab3ce6be29737a2afdad58ea85a5`.
- Independently verified the public wheel and source-distribution SHA-256 hashes and a clean `sdetkit==1.2.0` installation.

## [1.1.0] — Unpublished superseded candidate

Release candidate frozen: 2026-06-30. It was never tagged or published and was superseded after the full product scope advanced.

- Added structured diagnosis and review-first verification evidence.
- Added read-only JavaScript, TypeScript, and Go adapters.
- Added exact-wheel qualification on Python 3.10, 3.11, and 3.12.
- Added SHA-bound canonical adoption replay evidence.
- Improved quality, packaging, workflow, and documentation contracts.

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
