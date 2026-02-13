# CI Contract

## Blocking workflows
- **CI** (`.github/workflows/ci.yml`) is the primary PR blocking gate.
- It validates fast post checks on PRs (`tools/post_checks_fast.sh`) plus package build/smoke install, repo check, coverage, and docs build.

## Informational workflows
- **Quality** is schedule/manual for extended visibility and trend checks.
- **Mutation tests**, **SBOM**, **Dependency Audit**, and **OSV** provide security/quality signals and artifacts.

## Artifact expectations
- Repo audit JSON report (`report.json`) from CI.
- Dependency audit JSON (`pip-audit-report.json`) artifact.
- CycloneDX SBOM (`sbom.cdx.json`) artifact.

## Offline-by-default policy
- Test suite blocks real network by default via `tests/conftest.py`.
- Network tests must opt in with `@pytest.mark.network`.

## Local parity commands
- Fast lane: `bash tools/post_checks_fast.sh`
- Full strength: `bash tools/post_checks.sh`
- Coverage/docs gate: `bash quality.sh cov`

## Release strength checks
- Release workflow invokes `tools/post_checks.sh --release-tag <tag>` to include build/twine and tag/version verification.
