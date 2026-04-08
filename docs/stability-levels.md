# Stability levels (boundary declaration)

## Why this page exists

This page declares the current product boundary so adopters and contributors can make consistent decisions about what is primary vs secondary without guesswork.

## Flagship promise

DevS69 SDETKit's flagship promise is:

> **Deterministic release confidence / shipping readiness for software teams.**

## This page is a declaration, not a refactor

This is a policy and guidance page. It does **not** rename commands, remove aliases, move modules, or change CLI behavior.

## Tier definitions

### Public / stable

Primary surfaces for release-confidence decisions. This is the default path for new adopters and the strongest compatibility commitment.

### Advanced but supported

Supported surfaces for deeper rollout, integrations, operations, and guided adoption workflows. These are production-usable, with more iterative UX and documentation evolution than the public/stable tier.

### Experimental / incubator

Opt-in surfaces for incubator and transition-era workflows. Useful for advanced users, but expected to evolve faster.

## Current classification of the product surface

### Public / stable (default)

- Canonical release-confidence path: `gate fast` -> `gate release` -> `doctor`
- Core decision support commands and evidence lane: `gate`, `doctor`, `security`, `evidence`
- Canonical wrapper lane: `scripts/ready_to_use.sh quick|release`
- First-proof and adoption-critical docs (README start-here path, docs index start-here path, release-confidence explainer)

### Advanced but supported

- Broader operational and governance families (for example: `repo`, `ci`, `policy`, `report`, `maintenance`, `ops`)
- Integration and ecosystem connectors (for example: `agent`, notify/plugin/integration quickstarts)
- Guided rollout and organizational playbook families
- Secondary advanced/reference documentation used after the canonical first-proof path is trusted

### Experimental / incubator

- Impact/closeout and other transition-era command lanes
- Hidden/legacy long-tail command families intended for explicit opt-in use
- Archive/history-heavy material that remains available for context and continuity

## Compatibility expectations by tier

- **Public / stable:** highest compatibility expectation; changes should be deliberate, documented, and migration-aware.
- **Advanced but supported:** supported for real use, but command ergonomics, docs flow, and supporting interfaces may iterate faster.
- **Experimental / incubator:** best-effort continuity with faster evolution; validate in your repo/CI before treating as a hard dependency.

When lower-level CLI/help labels are more granular, this page should be read as the higher-level product policy, not a command-contract rewrite.

Root CLI help maps to these tiers as display guidance: canonical `gate fast` -> `gate release` -> `doctor` is shown as **Public / stable**, broader kits/operations/playbooks as **Advanced but supported**, and transition-era lanes as **Experimental / incubator**.

## What this page does NOT mean

- Not a deprecation wave.
- Not immediate command renames.
- Not feature removal.
- Not a breaking refactor.

## How to use this page

### For adopters

1. Start in **Public / stable** to get deterministic shipping readiness signals.
2. Add **Advanced but supported** surfaces as your rollout matures.
3. Use **Experimental / incubator** only with explicit validation and local/CI proof.

### For contributors

1. Protect **Public / stable** behaviors and docs clarity first.
2. Keep **Advanced but supported** improvements practical and backwards-aware.
3. Keep **Experimental / incubator** changes clearly labeled and non-disruptive to default onboarding.

## See also

- [Productization map](productization-map.md)
- [Versioning and support posture](versioning-and-support.md)
- [Integrations and extension boundary](integrations-and-extension-boundary.md)
- [Capability map and command taxonomy](command-taxonomy.md)
