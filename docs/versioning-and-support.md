# Versioning and support posture (current policy)

SDETKit's flagship promise remains:

> **Release confidence / shipping readiness for software teams.**

This page is the operational policy for versioning, compatibility, support, and
deprecation. It intentionally avoids guarantees we do not operationally enforce.

## Scope and intent

- This is a **current policy** for maintainers and adopters.
- It complements command docs and release workflow docs.
- Tier definitions live in [stability-levels.md](stability-levels.md); this page
  defines versioning/support behavior against those tiers.

## Versioning expectations

- SDETKit uses semantic version format (`MAJOR.MINOR.PATCH`).
- Current maintainer intent:
  - `PATCH` for fixes/docs/internal non-breaking improvements.
  - `MINOR` for backward-compatible feature growth.
  - `MAJOR` for deliberate breaking changes.
- Treat this as practical project policy, not a legal compatibility SLA.

## Compatibility and support posture by tier

- **Public / stable:** primary compatibility target and strongest change-control
  expectation for release-confidence flows.
- **Advanced but supported:** supported for production use, but docs/ergonomics
  and integration-facing edges may iterate faster.
- **Experimental / incubator:** opt-in and best-effort continuity; validate in
  your own repo/CI before treating as a hard dependency.

This posture does not mean every command has the same change velocity.
Compatibility expectations are intentionally tier-aware.

## Deprecation approach (current)

- No blanket deprecation SLA/timeline is promised across all surfaces.
- Preferred approach:
  1. Mark direction in docs/CLI help/changelog where practical.
  2. Keep compatibility aliases/wrappers during transition windows when
     feasible.
  3. Remove or tighten behavior deliberately in a major version when impact is
     material.
- Some transition-era commands remain available for auditability and migration.

## Maintainer release/changelog hygiene

When a change can affect compatibility expectations (behavior, outputs, install
path, or integration-facing interfaces), release notes should:

1. Name the affected tier (**Public / stable**, **Advanced but supported**, or
   **Experimental / incubator**).
2. State whether the change is backward-compatible or transitionary.
3. Keep wording aligned with this page and [stability-levels.md](stability-levels.md).

## Related references

- [stability-levels.md](stability-levels.md)
- [integrations-and-extension-boundary.md](integrations-and-extension-boundary.md)
- [release-confidence.md](release-confidence.md)
- [command-surface.md](command-surface.md)
- [releasing.md](releasing.md)
- [release-verification.md](release-verification.md)
