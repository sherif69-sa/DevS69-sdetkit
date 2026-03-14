# Integrations and extension boundary

SDETKit's flagship identity remains:

> **Release confidence / shipping readiness for software teams.**

This page defines practical ecosystem boundaries so future growth stays useful without bloating the core.

## Boundary model

Use this mental model when deciding where commands, docs, and workflows should live:

1. **Stable/Core** = default release-confidence path for most teams.
2. **Integrations** = optional environment/platform wiring around core checks.
3. **Playbooks** = guided rollout/adoption operating lanes.
4. **Experimental / transition-era** = incubator or historical lanes kept available but secondary.

For formal tier definitions, see [stability-levels.md](stability-levels.md) and [versioning-and-support.md](versioning-and-support.md).

## What belongs in Stable/Core

Put something in **Stable/Core** when it is broadly applicable to everyday shipping-readiness decisions:

- Core gate/security/doctor/evidence workflows used across repository types.
- Deterministic pass/fail or policy outputs relied on for go/no-go decisions.
- Installation and first-run docs that all adopters need.

Core should stay focused on the default path (`quick` then `release`) and should avoid platform- or vendor-specific assumptions.

## What belongs in Integrations

Put something in **Integrations** when it connects core signals into a specific delivery environment:

- CI provider wiring, artifact upload conventions, and external notification paths.
- Adopter-facing guidance for using SDETKit in another repository or platform.
- Optional integrations that depend on third-party services or environment-specific credentials.

Integrations should reuse Stable/Core command outputs rather than redefining core decision logic.

## What belongs in Playbooks

Put something in **Playbooks** when it guides how teams adopt or operate, instead of adding a new core decision primitive:

- Rollout sequencing and team operating patterns.
- Onboarding and contribution guidance.
- Scenario- or organization-specific execution narratives.

Playbooks may iterate faster than core command docs as long as they stay aligned with the current stability and support posture.

## What remains Experimental / transition-era

Keep material in **Experimental** (or explicitly transition-era) when it is:

- New and not yet proven across multiple adoption contexts.
- Historical impact/impact/closeout content preserved for auditability.
- Advanced or niche lanes that are useful for some users but not core onboarding.

Do not remove this content by default; keep it available but clearly secondary in high-traffic docs.

## Optional dependencies and optional integrations

SDETKit keeps optional dependencies as opt-in extras (`dev`, `test`, `docs`, `packaging`, `telegram`, `whatsapp`).

Practical policy:

- Stable/Core usage should not require optional integrations.
- Optional extras should be documented with explicit "use when" context.
- Integration-specific dependencies should stay isolated from default install paths.

See installation guidance in [install.md](install.md) and [ready-to-use.md](ready-to-use.md).

## How to add future integrations/extensions safely

When proposing a new integration or extension surface:

1. Prove value using existing Stable/Core outputs first.
2. Keep the integration optional and environment-scoped.
3. Document setup, failure modes, and rollback/disable path.
4. Cross-link stability tier and versioning/support implications.
5. Avoid adding hard dependencies to the default core install unless broadly required.

## Maintainer guardrails (what to avoid)

Maintainers should avoid:

- Promoting niche/vendor-specific integrations into Stable/Core too early.
- Treating experimental or transition-era lanes as stable compatibility promises.
- Expanding optional surfaces without matching docs/policy updates.
- Introducing new extension claims (for example, a formal plugin API promise) unless truly implemented and supported.

If uncertain, keep new capability in Integrations or Experimental first, gather adoption evidence, then promote deliberately.

## Related references

- [stability-levels.md](stability-levels.md)
- [versioning-and-support.md](versioning-and-support.md)
- [command-surface.md](command-surface.md)
- [adoption.md](adoption.md)
- [recommended-ci-flow.md](recommended-ci-flow.md)
