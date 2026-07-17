# Current product delta

Contract: [`docs/contracts/current-product-delta.v1.json`](contracts/current-product-delta.v1.json)

## Release truth

| Surface | Current truth |
|---|---|
| Published package | `sdetkit==1.0.3` |
| Repository package metadata | `1.2.0` candidate |
| Previous candidate | `1.1.0` was frozen but never tagged or published and is superseded |
| Candidate state | full-product scope established; exact-head qualification pending |
| Public 1.2.0 installation | not yet verified |

The README intentionally remains pinned to `sdetkit==1.0.3` until 1.2.0 is published and independently verified.

## Candidate scope

The 1.2.0 candidate represents the complete integrated product on `main`: exact failure extraction, shared FailureVector diagnosis, review-first SafetyGate decisions, protected verification, trajectory and RepoMemory evidence, deterministic operator reporting, release and merge readiness, and read-only adoption-to-diagnosis support across Python, JavaScript/TypeScript, Go, Rust, Java, .NET, and C++.

It also includes conservative CI-provider evidence for GitHub Actions, GitLab CI, Jenkins, and CircleCI, plus complete C++ and mixed-language monorepo operator proofs.

The stable first path remains:

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

## Exact-head evidence

A commit cannot contain its own final SHA. The candidate workflow therefore binds generated artifacts to the workflow run's exact `head_sha`. The tag-driven release workflow separately builds once and qualifies the exact wheel on Python 3.10, 3.11, and 3.12.

## Remaining release gates

1. Merge the release-truth candidate metadata PR.
2. Freeze and qualify the exact 1.2.0 candidate SHA.
3. Verify the protected GitHub `pypi` environment and matching PyPI Trusted Publisher.
4. Create the immutable signed `v1.2.0` tag.
5. Complete public publication, digest verification, and clean installation.
6. Record the completed release in a post-release evidence PR and only then update README installation guidance.

## Authority boundary

This document does not authorize automated patching, merging, security dismissal, publication, or semantic-equivalence claims.
