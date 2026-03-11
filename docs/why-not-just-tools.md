# Why not just run separate tools? (SDETKit system value)

SDETKit should be evaluated as a **layered release-confidence and engineering-operations toolkit**, not as a claim that lint/test/security tools are insufficient on their own.

At its best, SDETKit gives teams a repeatable operator journey from local checks to release gates, with consistent policy decisions and evidence artifacts.

## 1) What SDETKit actually is

SDETKit includes a flagship release-confidence path (`ready_to_use`, `gate`, `security enforce`) and a broad command surface that also covers diagnostics, docs quality, onboarding, evidence workflows, operational reporting, and adoption helpers. See the command guide for examples spanning `doctor`, `repo`, `security`, `ops`, `report`, and more. 

In practice, this is a **toolkit with layers**:

1. Core go/no-go release gating
2. Repo health and operator diagnostics
3. Evidence and reporting artifacts
4. Adoption and onboarding workflows
5. Playbooks and advanced operational lanes

That breadth is deliberate: it supports real engineering workflows before, during, and after a release decision.

## 2) Major layers of value (using the real surface)

### Layer A — Core release confidence

This is the shortest path to the primary outcome: "is this repo ready to ship?"

- `bash scripts/ready_to_use.sh quick`
- `bash scripts/ready_to_use.sh release`
- `sdetkit gate fast`
- `sdetkit gate release`
- `sdetkit security enforce ...`

These commands define the deterministic gate flow used for local and CI release-confidence checks.

### Layer B — Engineering workflow operations

SDETKit extends beyond one gate command with operational tools teams repeatedly need:

- `sdetkit doctor` for environment/repo diagnostics
- `sdetkit repo ...` and repo audit workflows for repository health checks
- `sdetkit ci validate-templates` for CI template verification
- `sdetkit docs-qa` and `sdetkit docs-nav` for documentation quality/navigation integrity

This layer reduces ad-hoc shell scripting and "tribal runbook" drift.

### Layer C — Evidence, policy, and repeatability

SDETKit includes evidence-oriented and policy-aware flows:

- Evidence pack/reporting workflows
- Policy and baseline checks
- Determinism and security gate guidance

This is where SDETKit often adds the most system value compared with manually running individual tools: consistency of gate semantics and output artifacts.

### Layer D — Adoption, onboarding, and operator enablement

The command surface and docs include onboarding and contributor workflows (`onboarding`, `first-contribution`, contributor funnel, triage template validation, weekly review), plus integration guidance for CI and ecosystem tools.

This layer matters when a team wants standard adoption across multiple repos or contributors, not just one engineer's local setup.

### Layer E — Playbooks and advanced lanes

The project also contains playbook-style and strategy/operations material (release, governance, transformation, integration lanes). This can look "broad" at first glance, but it supports teams that treat release confidence as an ongoing operational program, not a one-time script.

## 3) Why not just use raw tools directly?

Using raw tools directly is often the right starting point. You get full control and minimal abstraction.

SDETKit adds value when teams need:

- **Orchestration:** one coherent path instead of manually sequencing many commands.
- **Deterministic policy flow:** stable pass/fail semantics for gates.
- **Repeatable operator UX:** consistent commands for local and CI users.
- **Evidence capture:** reusable artifacts for audits, reviews, and handoffs.
- **Cross-repo standardization:** shared workflows across teams.
- **Adoption workflow:** explicit rollout/onboarding paths rather than one-off docs.
- **Built-in guidance:** playbooks and operator documentation tied to command outcomes.

## 4) Why the broader function surface exists (and its tradeoff)

A broad surface exists because real operator journeys are broad:

- Prepare environment and repository
- Run confidence and security gates
- Capture evidence
- Triage failures
- Onboard new contributors
- Standardize and scale workflows across repos

**Tradeoff:** breadth introduces complexity. Discoverability and command selection can be harder than in a single-purpose CLI.

SDETKit is most credible when users start with the flagship path and adopt additional lanes incrementally.

## 5) When to use SDETKit

SDETKit is a good fit for:

- Single-repo owners who want a stricter, repeatable release go/no-go flow
- QA/SDET leads standardizing confidence checks across contributors
- Release/reliability-minded teams that need evidence and policy-backed decisions
- Platform/enablement teams rolling out common repo checks and release practices

## 6) When *not* to use SDETKit

SDETKit may be unnecessary if:

- Your repo is very small and simple, with minimal release risk
- Your team explicitly wants raw underlying tools and manual orchestration only
- You are unwilling to adopt opinionated gate/workflow conventions

## 7) Concrete comparison: manual toolchain vs SDETKit system

| Dimension | Manual toolchain approach | SDETKit system approach |
|---|---|---|
| Workflow assembly | Team manually wires lint/test/security commands and scripts | Predefined command lanes (`ready_to_use`, `gate`, `security`, `doctor`, docs/repo ops) |
| Consistency | Depends on each maintainer's scripts and habits | Shared command UX and deterministic gate semantics |
| Evidence/artifacts | Usually ad-hoc logs; artifact quality varies | Built-in evidence/report-oriented workflows and docs patterns |
| Policy/gating | Custom thresholds and exit behavior per repo | Standardized, policy-oriented release-confidence flow |
| Onboarding | New contributors learn local conventions by trial/error | Explicit docs and commands for onboarding/adoption |
| Scale across repos | High variance unless platform team enforces templates | Easier standardization using one toolkit and command contract |

The key distinction is not "more tools" vs "fewer tools." It is **system behavior**: repeatability, policy consistency, and operator experience across the release lifecycle.

## 8) SDETKit does not replace great underlying tools

SDETKit depends on strong underlying tooling and does not claim to replace it.

It is a coordination and operationalization layer that helps teams apply those tools in a consistent release-confidence system. Teams should still evaluate and improve the underlying linters, test suites, scanners, and CI foundations.

## Bottom line

SDETKit is most useful when release confidence is treated as an operational system, not a one-command utility. Its breadth is a feature when it maps to your real workflow; it is overhead if you only need a thin wrapper around a few standalone commands.
