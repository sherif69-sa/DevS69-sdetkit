# Current product delta

Contract: [`docs/contracts/current-product-delta.v1.json`](contracts/current-product-delta.v1.json)

## Release truth

| Surface | Current truth |
|---|---|
| Published package | `sdetkit==1.0.3` |
| Repository package metadata | `1.1.0` |
| Candidate state | frozen, not published |
| Public 1.1.0 installation | not yet verified |

The README intentionally remains pinned to `sdetkit==1.0.3` until 1.1.0 is published and independently verified.

## Candidate scope

The 1.1.0 candidate contains structured diagnosis, review-first safety decisions, read-only JavaScript/TypeScript and Go adapters, isolated proof, protected proof-chain integrity, trajectory evidence, and adoption intelligence.

The stable first path remains:

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

## Exact-head evidence

A commit cannot contain its own final SHA. The canonical adoption workflow therefore uploads replay evidence with `GITHUB_SHA` in the artifact name. The tag-driven release workflow separately builds once and qualifies the exact wheel on Python 3.10, 3.11, and 3.12.

## Remaining release gates

1. Verify the protected GitHub `pypi` environment and matching PyPI Trusted Publisher.
2. Merge the exact-head candidate PR.
3. Create a signed `v1.1.0` tag.
4. Complete public publication, digest verification, and clean installation.
5. Record the completed release in a post-release evidence PR.

## Authority boundary

This document does not authorize automated patching, merging, security dismissal, publication, or semantic-equivalence claims.
