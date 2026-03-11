# Stability levels (current policy)

SDETKit's flagship promise remains:

> **Release confidence / shipping readiness for software teams.**

This page defines the current stability labels used across docs and CLI help. It is intended to set clear expectations without changing existing commands or workflows.

## Stable/Core

- **Intended audience:** teams making day-to-day go/no-go release decisions.
- **Expected stability:** highest stability in this repository; this is the default starting path.
- **Support expectations:** prioritized for maintenance, docs clarity, and regression prevention.
- **Backward compatibility:** best-effort compatibility is expected for normal usage; changes should be deliberate and clearly documented.
- **How to use in production:** safe as the primary production lane for release confidence checks.

Typical examples include `gate`, `doctor`, `security`, `evidence`, and `scripts/ready_to_use.sh quick|release`.

## Integrations

- **Intended audience:** teams connecting SDETKit to CI platforms, notifications, plugins, or external automation.
- **Expected stability:** stable for practical adoption, with occasional environment-specific adjustments.
- **Support expectations:** maintained and documented, but behavior can depend on third-party systems.
- **Backward compatibility:** best-effort compatibility with clear migration notes when interfaces evolve.
- **How to use in production:** recommended when integration points are validated in your own environment.

## Playbooks

- **Intended audience:** teams adopting guided rollout lanes (onboarding, contribution, reliability storytelling, governance execution).
- **Expected stability:** generally usable and supported, but more iterative than core gate commands.
- **Support expectations:** maintained as practical guidance with incremental improvements.
- **Backward compatibility:** command availability is expected, while workflows and narrative output can evolve.
- **How to use in production:** use for operational rollout and enablement, alongside stable/core release gates.

## Experimental

- **Intended audience:** advanced users and maintainers exploring incubator lanes or historical day/closeout flows.
- **Expected stability:** lower stability and faster iteration; not the first stop for new adopters.
- **Support expectations:** best-effort maintenance; focus is learning, transition support, and preserving historical value.
- **Backward compatibility:** may change more quickly, though breaking changes should still be communicated where practical.
- **How to use in production:** treat as opt-in and validate locally/in CI before relying on it for critical release decisions.

This includes many day/cycle/closeout lanes. They remain available as transition-era and advanced playbook material, not removed.

## Usage guidance

1. Start with **Stable/Core** for release confidence and shipping readiness decisions.
2. Add **Integrations** to embed checks into your delivery systems.
3. Use **Playbooks** for guided adoption and organizational rollout.
4. Use **Experimental** lanes intentionally, with explicit validation.

See also:

- [Productization map](productization-map.md)
- [Capability map and command taxonomy](command-taxonomy.md)
