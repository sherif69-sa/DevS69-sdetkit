# Versioning and support posture (current policy)

SDETKit's flagship promise remains:

> **Release confidence / shipping readiness for software teams.**

This page documents the **current** trust-and-governance posture for versions,
compatibility, support, and deprecation. It is intentionally compact and avoids
promises that are not yet operationally guaranteed.

## Scope and intent

- This is a **current policy** for users and maintainers.
- It complements (not replaces) command docs, release workflow docs, and
  stability-level guidance.
- Where needed, this page uses terms like **intended direction** and
  **best-effort** to stay honest about present-day guarantees.

## Versioning expectations

- SDETKit uses a semantic version format (`MAJOR.MINOR.PATCH`) as the current
  release convention.
- Current intent:
  - `PATCH` for fixes/docs/internal non-breaking improvements.
  - `MINOR` for backward-compatible feature growth.
  - `MAJOR` for deliberate breaking changes.
- Versioning is maintained with release process checks, but users should treat
  this as a practical maintainer policy rather than a legal compatibility SLA.

## Compatibility expectations

- **Stable/Core** commands and workflows are the primary compatibility target.
- Integrations and playbooks are supported with best-effort compatibility,
  recognizing third-party/environment variability.
- Experimental and transition-era lanes may evolve faster and should be
  validated before production reliance.
- Compatibility expectations are intentionally tied to stability tiers rather
  than assuming all surfaces have the same change velocity.

## Stability tiers and what they imply

- **Stable/Core:** highest confidence for day-to-day release gating and shipping
  readiness checks.
- **Integrations:** suitable for production use after local/CI validation in
  your environment.
- **Playbooks:** supported and useful, but expected to iterate more than core
  gates.
- **Experimental:** opt-in, best-effort maintenance, and faster evolution.

For tier definitions and rollout guidance, see
[stability-levels.md](stability-levels.md).

## Deprecation approach (current)

- No blanket hard timeline is promised for all deprecations.
- Preferred approach:
  1. Mark direction clearly in docs/CLI help/changelog where practical.
  2. Keep compatibility aliases/wrappers during transition windows when
     feasible.
  3. Remove or tighten behavior deliberately in a major version when impact is
     material.
- Some historical and transition-era commands remain intentionally available for
  auditability and migration support.

## What users should treat as stable vs evolving

Treat as most stable for production rollout:

- Core release-confidence flow (`quick` then `release`).
- Core gate/security/doctor/evidence command families.
- Published installation and release-validation docs.

Treat as evolving (validate before broad dependence):

- Environment-specific integration edges.
- Guided playbook narratives and transition-era/day closeout lanes.
- Newer or explicitly experimental command families.

## Related references

- [stability-levels.md](stability-levels.md)
- [release-confidence.md](release-confidence.md)
- [command-surface.md](command-surface.md)
- [releasing.md](releasing.md)
- [release-verification.md](release-verification.md)
