# Changelog

## Unreleased

No changes after the release-candidate freeze.

## [1.1.0]

Release candidate frozen: 2026-06-30

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
