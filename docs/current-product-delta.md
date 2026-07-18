# Current product delta

Contract: [`docs/contracts/current-product-delta.v1.json`](contracts/current-product-delta.v1.json)

## Release truth

| Surface | Current truth |
|---|---|
| Published package | `sdetkit==1.2.0` |
| Repository package metadata | `1.2.0` |
| Previous candidate | `1.1.0` was frozen but never tagged or published and is superseded |
| Release state | `v1.2.0` published and independently verified |
| Source SHA | `5165a82f8cd2ab3ce6be29737a2afdad58ea85a5` |

The README and installation documentation now pin to `sdetkit==1.2.0`. Distribution hashes, the clean public installation, and the GitHub Release are recorded in the [public release verification log](release-verification.md).

## Published scope

The 1.2.0 release represents the complete product qualified from the immutable tag: exact failure extraction, shared FailureVector diagnosis, review-first SafetyGate decisions, protected verification, trajectory and RepoMemory evidence, deterministic operator reporting, release and merge readiness, and read-only adoption-to-diagnosis support across Python, JavaScript/TypeScript, Go, Rust, Java, .NET, and C++.

It also includes conservative CI-provider evidence for GitHub Actions, GitLab CI, Jenkins, and CircleCI, plus complete C++ and mixed-language monorepo operator proofs.

The stable first path remains:

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

## Exact-head evidence

The immutable `v1.2.0` tag resolves to source commit `5165a82f8cd2ab3ce6be29737a2afdad58ea85a5`. The release workflow built the distributions once, qualified the exact wheel on Python 3.10, 3.11, and 3.12, produced GitHub provenance, and published through PyPI Trusted Publishing.

Independent post-publication verification matched the public filenames and SHA-256 digests to the workflow manifest and installed `sdetkit==1.2.0` successfully from the public PyPI index.

## Release gates

All 1.2.0 release gates are complete:

1. release truth reconciled;
2. exact candidate SHA qualified;
3. protected `pypi` environment and Trusted Publisher verified;
4. immutable `v1.2.0` tag created;
5. public distributions published and attested;
6. filenames, digests, and clean installation independently verified;
7. GitHub Release created from the exact workflow artifacts.

Changes merged after `v1.2.0` are unreleased until a later qualified publication.

## Authority boundary

This document does not authorize automated patching, merging, security dismissal, future publication, or semantic-equivalence claims.
