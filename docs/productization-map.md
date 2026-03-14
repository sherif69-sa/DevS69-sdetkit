# Productization map: release confidence / shipping readiness

## Purpose

This document is a **product-boundary audit** of the current repository and a concrete map for evolving SDETKit into a globally adoptable product centered on one flagship promise:

> **Release confidence / shipping readiness for software teams.**

This is an inspection and planning artifact. It does **not** propose broad refactors or functionality removal.

## 1) Current-state audit

## Repository shape (what exists today)

- Runtime package code sits in `src/sdetkit/` with a very broad command surface routed by `src/sdetkit/cli.py`.
- The top-level UX is already release-confidence oriented in `README.md` (`ready_to_use.sh quick` and `ready_to_use.sh release`).
- Documentation is extensive (`docs/`), but currently mixes:
  - core user journeys,
  - reference docs,
  - integration guides,
  - a large archive of impact-based reports and closeout pages.
- `scripts/` includes both core workflows (`ready_to_use.sh`, `check.sh`, `bootstrap.sh`) and many impact-specific contract checks.

## Package and command surface observations

## Stable/public-facing feeling areas

These appear closest to stable product surface:

- Core release flow:
  - `gate`, `doctor`, `security`, `evidence`
  - wrapper script `scripts/ready_to_use.sh` with `quick` and `release` lanes.
- Supporting operational surface:
  - `repo`, `ci`, `maintenance`, `policy`, `report`, `production-readiness`.
- Practical utility commands with clear contracts:
  - `kv`, `apiget`, `patch`, `cassette-get`.

## Confusing/overlapping/internal-feeling areas

- Very large set of impact/closeout command modules in `src/sdetkit/` (for example `day28_*` through `day97_*` and many `*_closeout` modules).
- CLI has to hide many commands from main help, which is itself a signal that product boundaries are still blurred.
- Docs navigation includes strong flagship pages plus a very large historical/report corpus in the same visible namespace.
- Command naming has overlap in places (`weekly-review`, `weekly-review-lane`, impact-specific closeouts), which can feel incubator-like to external adopters.

## 2) Classification of current contents (core / integrations / playbooks / experimental)

Classification is based on current repository contents and naming patterns.

## Core

**Definition:** mandatory, high-confidence paths directly tied to release confidence / shipping readiness.

- Runtime commands and modules:
  - `gate`, `doctor`, `security`, `evidence`, `production_readiness`, `repo`, `ci`, `policy`, `report`.
- Wrapper workflows:
  - `scripts/ready_to_use.sh`, `ci.sh`, `quality.sh`, `security.sh`, `scripts/check.sh`.
- Primary docs:
  - `README.md`, `docs/index.md`, `docs/ready-to-use.md`, `docs/release-confidence.md`, `docs/decision-guide.md`, `docs/recommended-ci-flow.md`, `docs/adoption.md`, `docs/adoption-troubleshooting.md`.

## Integrations

**Definition:** ecosystem connectors and platform-specific interoperability that extend the core.

- CLI/module areas:
  - `agent/*`, `notify`, `notify_plugins`, `plugin_system`, `plugins`, `github_actions_quickstart`, `gitlab_ci_quickstart`, `n8n` docs, omnichannel/bridge docs.
- Packaging extras and entry points indicating external systems:
  - optional dependencies for Telegram and WhatsApp.
- Example integration assets:
  - `examples/ci/*`, template-related CI docs/pages.

## Playbooks

**Definition:** guided rollout/use-case workflows for adoption and organizational execution.

- Named playbook modules:
  - `onboarding`, `weekly_review`, `demo`, `proof`, `first_contribution`, `contributor_funnel`, `triage_templates`, `startup_use_case`, `enterprise_use_case`.
- Rollout-oriented narrative modules:
  - `release_narrative`, `release_readiness_board`, `reliability_evidence_pack`, `quality_contribution_delta`, `faq_objections`, `community_activation`, `external_contribution_push`, `kpi_audit`.
- Playbook discovery/routing:
  - `playbooks_cli.py`, `sdetkit playbooks`.

## Experimental

**Definition:** incubator/history-heavy surfaces that are useful but should not define first-time product identity.

- Most `dayNN_*` and `*_closeout` modules in `src/sdetkit/`.
- Day-based contract scripts in `scripts/check_day*.py` and impact-specific closeout checks.
- Large archive of impact-based docs and integration closeout pages in `docs/`.
- Long-tail command aliases and hidden command behavior currently needed to keep main help usable.

## 3) Public/stable vs unclear boundary statement

## Treat as public/stable now

- `sdetkit gate ...`
- `sdetkit doctor ...`
- `sdetkit security ...`
- `sdetkit evidence ...`
- `sdetkit repo ...`
- `sdetkit ci ...`
- `scripts/ready_to_use.sh quick|release`

## Treat as "advanced but supported"

- `policy`, `report`, `maintenance`, `ops`, `notify`, `agent`, integration quickstarts.

## Treat as incubator/legacy lane (explicit opt-in)

- Day/impact/closeout command family and matching impact-report documentation.
- Campaign-style command names where scope is phase-specific rather than evergreen.

## 4) Proposed target taxonomy (for future productization)

Keep implementation mostly where it is for now, but define a target taxonomy to guide future incremental changes.

## Runtime package taxonomy (target)

```text
sdetkit/
  core/           # release gate, doctor, security, evidence, readiness contracts
  integrations/   # CI providers, chat/notify adapters, external connectors, plugin adapters
  playbooks/      # guided onboarding, rollout, adoption, governance playbooks
  experimental/   # incubator lanes, impact/impact closeouts, unstable aliases
  cli/            # user-facing command routing (thin), help profiles, command visibility policy
```

Notes:
- This is a target map, not a migration request in this PR.
- Existing modules can be progressively wrapped/aliased into this taxonomy over multiple small PRs.

## CLI taxonomy (target)

Top-level command groups should converge toward:

1. `sdetkit core ...` (or continue top-level aliases) for release-confidence essentials.
2. `sdetkit integrations ...` for external systems/platform connectors.
3. `sdetkit playbooks ...` for guided outcomes.
4. `sdetkit experimental ...` for explicit incubator access.

Maintain backwards compatibility by keeping existing commands as aliases during transition.

## 5) Proposed docs information architecture (few top-level journeys)

Recommended top-level docs journeys:

1. **Start here (5 minutes)**
   - Quick confidence, release gate, and first pass/fail interpretation.
2. **Adopt in CI/CD**
   - GitHub/GitLab/Jenkins templates, rollout order, troubleshooting.
3. **Operate at scale**
   - Evidence packs, policy, reporting, governance patterns.
4. **Integrations**
   - Notifications, agent/automation bridges, plugin adapters.
5. **Playbooks**
   - Outcome-based guided lanes (onboarding, contribution, reliability narratives, etc.).
6. **Experimental / archive**
   - Day/impact closeout history and incubator commands, clearly marked as non-primary.

Practical IA rule:
- Keep only journeys 1-4 prominently in README and docs landing pages.
- Link playbooks as guided optional paths.
- Keep experimental/archive content accessible but visually de-emphasized.

## 6) Recommended follow-up sequence (next PRs)

1. **Boundary declaration PR**
   - Add a concise "stability levels" doc and link it from README + docs index.
2. **CLI discoverability PR**
   - Introduce clearer help grouping that labels commands as Core / Integrations / Playbooks / Experimental.
3. **Docs IA PR**
   - Reorganize MkDocs nav to foreground 3-5 flagship journeys and move impact/impact history under archive sections.
4. **Compatibility PR**
   - Add explicit alias/compatibility matrix for legacy impact/closeout commands.
5. **Incremental module convergence PRs**
   - Move only a few modules at a time toward target taxonomy with tests and deprecation notes.

## 7) Key risks and ambiguities

- **Risk: product identity dilution.** The breadth of commands and impact-history artifacts can overshadow the flagship release-confidence promise.
- **Risk: accidental breaking change.** Aggressive command cleanup could break existing automation that depends on legacy names.
- **Risk: docs overload for first-time users.** Too many equally prominent pages slows adoption.
- **Ambiguity: long-term status of impact/closeout modules.** Need maintainers to decide: archive-only, supported-long-tail, or scheduled deprecation.
- **Ambiguity: naming end-state.** Whether to keep flat top-level commands forever or migrate to grouped command namespaces with aliases.

## 8) Decision checkpoints for maintainers

Before implementation-heavy refactors, explicitly decide:

1. Which commands are "public/stable" with compatibility guarantees.
2. Which commands are "supported/advanced" without long-term frozen interfaces.
3. Which commands are "experimental/incubator" and may change quickly.
4. Documentation SLA for each tier (full docs vs brief reference vs archive-only).

Those decisions will reduce future refactor risk and let SDETKit scale as a product with a clearer boundary contract.
