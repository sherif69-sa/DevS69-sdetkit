# Versioning and support posture (current policy)

SDETKit's flagship promise remains:

> **Release confidence / shipping readiness for software teams through one canonical command path.**

Primary outcome: know if a change is ready to ship from explicit evidence.
Canonical first path: `python -m sdetkit gate fast` -> `python -m sdetkit gate release` -> `python -m sdetkit doctor`.

This page is the operational policy for versioning, compatibility, support, and
deprecation. It intentionally avoids guarantees we do not operationally enforce.

## Quick support snapshot

- **Supported Python floor:** **3.10+**
- **Preferred install mode:** isolated environments (`venv` or `pipx`)
- **First dependency target for adopters:** canonical command path artifacts and decision flow
- **Support model:** best-effort public support (no contractual SLA stated in project policy)

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

## What adopters should depend on first

For release-confidence decisions, depend on this order first:

1. Canonical commands and flow:
   - `python -m sdetkit gate fast`
   - `python -m sdetkit gate release`
   - `python -m sdetkit doctor`
2. Canonical artifact outputs used for triage and CI evidence:
   - `build/gate-fast.json`
   - `build/release-preflight.json`
3. Public documentation for tier boundaries and command-surface intent.

This ordering keeps integrations aligned with the most stable, adopter-facing contract.

## Stability and support boundaries

### Public / stable

Intended as the strongest compatibility target and primary compatibility target for production adoption.

You can generally treat these as the first surfaces to automate against:
- canonical release-confidence flow
- core evidence and decision lane behavior
- user-facing docs describing canonical usage

### Advanced but supported

Supported for real production use, but expected to iterate faster than public/stable surfaces.

Typical changes here may include:
- docs/UX refinements
- integration ergonomics
- broader operational and rollout helpers

Adopters can depend on this tier, but should expect more frequent incremental adjustments.

### Experimental / incubator

Opt-in and best-effort continuity only.

Treat this tier as subject to faster change and require explicit local/CI validation before making it a hard dependency in organizational workflows.

## Canonical path vs compatibility lanes (visibility policy)

For first-time adoption and release-confidence proof, use the canonical path:

1. `python -m sdetkit gate fast`
2. `python -m sdetkit gate release`
3. `python -m sdetkit doctor`

Compatibility surfaces remain supported, including umbrella kits and
backward-compatible aliases used by existing automation. Their continued
availability preserves transition continuity and advanced workflows, but does
**not** make them the primary first-time recommendation.

This section is guidance visibility only. It is **not** a new deprecation wave,
removal announcement, or command-behavior change.

## Best-effort / subject-to-change areas

Without changing documented tier policy, adopters should treat the following as
higher-iteration or best-effort compared with canonical public/stable paths:

- experimental/incubator and transition-era lanes
- hidden/legacy-oriented command families
- secondary/advanced docs and rollout playbooks used after first-proof adoption

When in doubt, anchor automations to canonical command flow + documented artifacts first.

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

- [support.md](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/SUPPORT.md)
- [stability-levels.md](stability-levels.md)
- [integrations-and-extension-boundary.md](integrations-and-extension-boundary.md)
- [release-confidence.md](release-confidence.md)
- [command-surface.md](command-surface.md)
- [releasing.md](releasing.md)
- [release-verification.md](release-verification.md)
