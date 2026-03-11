# SDETKit Capability Map and Command Taxonomy

SDETKit has a deliberately broad CLI surface. That breadth is a feature (you can stay in one toolkit from first local confidence check to governance-grade evidence), but it also creates discoverability cost for new users.

This page is a navigation model for the **real** command surface so users can quickly answer:

- what should I use first?
- what is core vs supporting vs advanced?
- which commands are daily vs occasional?

## Mental model: five functional layers

Use these layers as a map, not as hard boundaries. Some commands legitimately sit between layers.

## 1) Core release confidence (start here)

This is the primary value path for most teams: "is this repo ready to ship?"

- `sdetkit gate fast`
- `sdetkit gate release`
- `sdetkit doctor`
- `sdetkit security ...` (especially `security enforce`)
- `sdetkit evidence pack`
- `sdetkit playbooks` (as a router to guided adoption flows)

**Typical use frequency:** daily to per-PR.

**Why this is core:** these commands are the fastest route to deterministic pass/fail confidence and release go/no-go evidence.

## 2) Evidence, policy, and reporting (governance support)

Use this layer when teams need policy accountability, trend visibility, and auditable artifacts beyond one run.

- `sdetkit policy ...` (`snapshot`, `check`, `diff`)
- `sdetkit report ...` (`ingest`, `dashboard`, `build`, `recommend`)
- `sdetkit evidence pack`
- `sdetkit roadmap ...` (planning/status structure)
- `sdetkit docs-qa`, `sdetkit docs-nav` (docs quality and navigation validation as release evidence support)

**Typical use frequency:** weekly, milestone, or release-cycle.

**Why this is supporting:** it strengthens release confidence decisions with traceability and longitudinal context.

## 3) Repo and engineering operations (execution layer)

This layer supports day-to-day engineering hygiene, automation, and controlled change operations.

- `sdetkit repo ...` (check/fix/init/audit/dev/projects/rules/policy/ops)
- `sdetkit dev ...` (shortcut into `repo dev` workflows)
- `sdetkit maintenance ...`
- `sdetkit patch ...`
- `sdetkit ci validate-templates`
- `sdetkit kv`, `sdetkit apiget`, `sdetkit cassette-get`
- `sdetkit agent ...`, `sdetkit ops ...`, `sdetkit notify ...`

**Typical use frequency:** daily for maintainers/platform owners; occasional for evaluators.

**Why this is an operations layer:** these commands keep repos and workflows healthy so release-confidence gates remain reliable.

## 4) Adoption, onboarding, and rollout playbooks (guided outcomes)

This layer packages common org goals into command-led playbooks.

Representative commands:

- `sdetkit onboarding`
- `sdetkit first-contribution`
- `sdetkit contributor-funnel`
- `sdetkit triage-templates`
- `sdetkit startup-use-case`, `sdetkit enterprise-use-case`
- `sdetkit github-actions-quickstart`, `sdetkit gitlab-ci-quickstart`
- `sdetkit weekly-review`
- `sdetkit demo`, `sdetkit proof`
- `sdetkit quality-contribution-delta`, `sdetkit reliability-evidence-pack`, `sdetkit release-readiness-board`, `sdetkit release-narrative`, `sdetkit trust-signal-upgrade`, `sdetkit faq-objections`, `sdetkit onboarding-time-upgrade`, `sdetkit community-activation`, `sdetkit external-contribution-push`, `sdetkit kpi-audit`

Use `sdetkit playbooks` to discover and choose the right guided lane.

**Typical use frequency:** occasional to campaign-based (not every PR).

## 5) Advanced / incubator lanes (broad, real, and intentionally not front-and-center)

SDETKit also includes a large set of hidden playbook-style commands (for example many `dayNN-*` and `*-closeout` commands). They are intentionally hidden from the main `--help` output to preserve a focused first-time experience, while still being runnable directly.

- Discoverability command: `sdetkit playbooks`
- Design intent: broad capability without making `sdetkit --help` unusably noisy.

**Typical use frequency:** specialized, program-phase specific.

---

## Core vs supporting vs advanced at a glance

- **Core (use first):** `gate`, `doctor`, `security`, `evidence`, base `playbooks` discovery.
- **Supporting (use to scale confidence):** `policy`, `report`, docs validation, repo/maintenance workflows.
- **Advanced (use intentionally):** ops/notify/agent integrations, long-tail playbooks, hidden day/closeout lanes.

## Daily vs occasional command cadence

- **Daily / per change:** `gate fast`, targeted `doctor`, selected `repo`/`dev`, sometimes `security enforce`.
- **Per release / weekly:** `gate release`, `evidence pack`, `policy check`, `report build/recommend`, weekly-review style playbooks.
- **Occasional / transformation phase:** onboarding and org rollout playbooks, incubator closeout/day commands.

## Recommended entry paths by role

### First-time evaluator

1. `sdetkit gate fast`
2. `sdetkit doctor --all --json`
3. `sdetkit gate release`
4. `sdetkit playbooks` (only after core path is clear)

### Repo maintainer

1. Daily: `sdetkit gate fast` + targeted `sdetkit repo ...`
2. Before merges/releases: `sdetkit security enforce ...` + `sdetkit gate release`
3. For audit trail: `sdetkit evidence pack` + `sdetkit report ...`

### QA/SDET lead

1. Standardize baseline with `gate`, `doctor`, `security`
2. Add org evidence posture via `evidence`, `policy`, `report`
3. Use selected playbooks (`weekly-review`, `release-readiness-board`, `reliability-evidence-pack`) for recurring governance rhythm

### Advanced operator

1. Start with `sdetkit playbooks` to select outcome-specific lanes
2. Use `ops`, `notify`, `agent`, and CI template validation for control-plane integration
3. Pull in hidden `dayNN-*` / `*-closeout` commands only when running explicit program phases

## Practical navigation rules

- If you are unsure, start in **Core release confidence**.
- If you need traceability over time, move to **Evidence/policy/reporting**.
- If you are automating repository mechanics, use **Repo and engineering operations**.
- If you are running adoption programs, choose **Playbooks**.
- If a command name looks campaign- or phase-specific (`dayNN`/`closeout`), treat it as **advanced/incubator** and opt in deliberately.

## Notes on judgment calls in this taxonomy

Some commands naturally cross layers:

- `evidence` appears in both core and governance contexts.
- `playbooks` is both a core discovery entry point and a bridge into advanced lanes.
- docs-focused commands (`docs-qa`, `docs-nav`) were placed under evidence/policy/reporting because they are frequently used as release-quality validation artifacts, even though they are also general docs tooling.

These placements are intentional to optimize navigation clarity, not to claim strict architectural isolation.
