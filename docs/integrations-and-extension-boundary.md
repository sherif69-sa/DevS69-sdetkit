# Integrations and extension boundary

SDETKit's flagship identity remains:

> **Release confidence / shipping readiness for software teams.**

This page defines practical ecosystem boundaries so future growth stays useful without bloating the core.

## Boundary model

Use this mental model when deciding where commands, docs, and workflows should live:

1. **Public / stable** = default release-confidence path for most teams.
2. **Advanced but supported** = optional environment/platform wiring and guided operating lanes around core checks.
3. **Experimental / incubator** = transition-era or historical lanes kept available but secondary.

For formal tier definitions, see [stability-levels.md](stability-levels.md) and [versioning-and-support.md](versioning-and-support.md).

## What belongs in Public / stable

Put something in **Public / stable** when it is broadly applicable to shipping-readiness decisions:

- Core gate/security/doctor/evidence workflows used across repository types.
- Deterministic pass/fail or policy outputs relied on for go/no-go decisions.
- Installation and first-run docs that all adopters need.

This tier should stay focused on the canonical first-time path (`gate fast` then `gate release` then `doctor`) and should avoid platform- or vendor-specific assumptions.

## What belongs in Advanced but supported

Put something in **Advanced but supported** when it connects core signals into a specific delivery environment or guided rollout flow:

- CI provider wiring, artifact upload conventions, and external notification paths.
- Adopter-facing guidance for using SDETKit in another repository or platform.
- Optional integrations that depend on third-party services or environment-specific credentials.

These lanes should reuse Public/stable command outputs rather than redefining core decision logic.

- Rollout sequencing and team operating patterns.
- Onboarding and contribution guidance.
- Scenario- or organization-specific execution narratives.

Guided adoption lanes may iterate faster than core command docs as long as they stay aligned with the current stability and support posture.

## What remains Experimental / incubator

Keep material in **Experimental** (or explicitly transition-era) when it is:

- New and not yet proven across multiple adoption contexts.
- Historical impact/impact/closeout content preserved for auditability.
- Advanced or niche lanes that are useful for some users but not core onboarding.

Do not remove this content by default; keep it available but clearly secondary in high-traffic docs.

## Optional dependencies and optional integrations

SDETKit keeps optional dependencies as opt-in extras (`dev`, `test`, `docs`, `packaging`, `telegram`, `whatsapp`).

Practical policy:

- Public/stable usage should not require optional integrations.
- Optional extras should be documented with explicit "use when" context.
- Integration-specific dependencies should stay isolated from default install paths.

See installation guidance in [install.md](install.md) and [ready-to-use.md](ready-to-use.md).

## How to add future integrations/extensions safely

When proposing a new integration or extension surface:

1. Prove value using existing Public/stable outputs first.
2. Keep the integration optional and environment-scoped.
3. Document setup, failure modes, and rollback/disable path.
4. Cross-link stability tier and versioning/support implications.
5. Avoid adding hard dependencies to the default core install unless broadly required.

## Maintainer guardrails (what to avoid)

Maintainers should avoid:

- Promoting niche/vendor-specific integrations into Public/stable too early.
- Treating experimental or transition-era lanes as stable compatibility promises.
- Expanding optional surfaces without matching docs/policy updates.
- Introducing new extension claims (for example, a formal plugin API promise) unless truly implemented and supported.

If uncertain, keep new capability in Advanced but supported or Experimental / incubator first, gather adoption evidence, then promote deliberately.

## Related references

- [stability-levels.md](stability-levels.md)
- [versioning-and-support.md](versioning-and-support.md)
- [command-surface.md](command-surface.md)
- [adoption.md](adoption.md)
- [recommended-ci-flow.md](recommended-ci-flow.md)
