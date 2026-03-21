# Automation bots and maintenance control loop

This page is the operational index for the repo's **maintenance bots**, especially the GitHub Advanced Security (GHAS) and upgrade-review automations that keep the project moving without waiting for a manual audit.

## Why these bots exist

The repo already exposes strong local/operator commands such as:

- `python -m sdetkit intelligence upgrade-audit --format json --top 10`
- `python -m sdetkit kits optimize --goal "upgrade umbrella architecture with agentos optimization" --format json`
- `python -m sdetkit kits expand --goal "add more helpful automation bots and GitHub Advanced Security coverage" --format json`

The bots turn those same maintenance signals into a recurring GitHub-native operating loop:

1. collect the state,
2. summarize the risk,
3. open or refresh an actionable issue,
4. point maintainers to the next safe validation lane.

## Current bot inventory

## Worker templates that align with the bot surface

In addition to scheduled GitHub bots, the repo now ships **AgentOS worker templates** that let maintainers run the same expansion/review loops on demand and keep the outputs deterministic:

- **`repo-expansion-control`** — runs `kits optimize` + `kits expand`, writes JSON artifacts, and bundles them for roadmap / dashboard follow-up.
- **`adapter-smoke-worker`** — validates optional notification adapters, captures integration-adapter route maps, and packages a quickstart-ready bundle.
- **`dependency-radar-worker`** — captures an offline-safe upgrade inventory, radar snapshot, and validation route map for refactor / dependency review.
- **`validation-route-worker`** — turns a package or domain query into a route map plus doctor-linked upgrade guidance.
- **`runtime-watchlist-worker`** — emits a runtime-core fast-follow watchlist plus a route map for the hottest runtime validation lanes.
- **`docs-search-radar`** — runs a strict MkDocs build, captures the build log, and bundles docs-search evidence for later review.
- **`release-readiness-worker`** — snapshots `doctor` plus `github_automation_check` so release-readiness follow-up can happen outside of a publish crunch.
- **`worker-alignment-radar`** — keeps expansion recommendations, automation coverage, and template inventory aligned with the repo's active worker surface.

Recommended local launches:

```bash
python -m sdetkit agent templates run repo-expansion-control
python -m sdetkit agent templates run adapter-smoke-worker
python -m sdetkit agent templates run dependency-radar-worker
python -m sdetkit agent templates run validation-route-worker --set query=httpx
python -m sdetkit agent templates run runtime-watchlist-worker
python -m sdetkit agent templates run docs-search-radar
python -m sdetkit agent templates run release-readiness-worker
python -m sdetkit agent templates run worker-alignment-radar
python -m sdetkit kits expand --goal "add more bots workers search and repo expansion" --format json
```

### Security and GitHub Advanced Security bots

- **`security.yml`** — runs CodeQL.
- **`osv-scanner.yml`** — runs OSV vulnerability scanning and uploads SARIF.
- **`dependency-audit.yml`** — runs `pip-audit` against the repo dependency surface.
- **`sbom.yml`** — refreshes SBOM coverage for downstream review.
- **`security-maintenance-bot.yml`** — creates the weekly maintenance checklist and weak-spot report.
- **`secret-protection-review-bot.yml`** — creates a weekly secret-protection review issue for push protection, delegated bypass, validity checks, and open secret-scanning backlog slices.
- **`ghas-review-bot.yml`** — creates the weekly GHAS digest issue with open-alert counts, workflow freshness, and follow-up prompts.
- **`ghas-campaign-bot.yml`** — creates a weekly GHAS campaign planner issue for Copilot Autofix-aware code scanning backlog slices, secret scanning age buckets, and push-protection follow-up.
- **`ghas-alert-sla-bot.yml`** — creates a weekly GHAS SLA tracker issue that forces 7/14/30-day backlog slices into an owned remediation lane.
- **`ghas-metrics-export-bot.yml`** — exports a weekly GHAS metrics artifact plus an issue-driven snapshot of alert totals, age buckets, and workflow freshness.
- **`ghas-codeql-hotspots-bot.yml`** — creates a weekly CodeQL hotspot issue that groups the code-scanning queue by rule and file so fixes can land in batches.
- **`security-configuration-audit-bot.yml`** — creates a monthly GHAS configuration audit issue covering repo-local workflow coverage, code security configuration visibility, and dependency submission posture.
- **`dependency-review.yml`** — blocks pull requests that introduce vulnerable dependencies or denied license drift before they merge.

### Dependency and repo-maintenance bots

- **`dependency-auto-merge.yml`** — auto-merges safe Dependabot updates after checks pass.
- **`pre-commit-autoupdate.yml`** — refreshes pre-commit hook pins.
- **`dependency-radar-bot.yml`** — publishes a recurring dependency radar issue plus a runtime fast-follow watchlist.
- **`adapter-smoke-bot.yml`** — publishes a weekly adapter smoke issue and artifact bundle for notification adapter quality and expansion readiness.
- **`repo-optimization-bot.yml`** — publishes a weekly repo-optimization control loop issue from `kits optimize`, `kits expand`, and the GitHub automation maintenance check.
- **`workflow-governance-bot.yml`** — publishes a monthly workflow-governance audit for permissions, SHA pinning, and manual recovery posture.
- **`docs-experience-bot.yml`** — publishes a weekly docs-experience radar issue plus JSON artifact covering navigation coverage, search posture, and flagship-doc visibility.
- **`release-readiness-radar-bot.yml`** — publishes a weekly release-readiness radar issue with doctor output, release asset freshness, and release-workflow coverage.
- **`runtime-watchlist-bot.yml`** — publishes a weekly runtime fast-follow issue and worker artifacts so hot-path runtime upgrades stay reviewable.
- **`worker-alignment-bot.yml`** — runs the aligned worker templates together and publishes a weekly worker/radar issue with deterministic artifact links.
- **`contributor-onboarding-bot.yml`** — keeps contributor guidance discoverable.
- **`pr-helper-bot.yml` / `pr-quality-comment.yml`** — keep pull requests reviewable and actionable.

## New additions in this upgrade

### `ghas-review-bot.yml`

This bot gives the repo a GHAS-native triage layer instead of relying on maintainers to click through the Security tab manually.

It now:

- counts open **code scanning**, **Dependabot**, and **secret scanning** alerts when the API is available,
- records workflow freshness for the main security automations,
- opens a date-scoped `🛡️ GHAS weekly digest (...)` issue,
- closes older GHAS digest issues automatically,
- degrades safely when an additional token is required for private security endpoints.

> Optional hardening: set `GHAS_READ_TOKEN` if you want the bot to use a token with broader security-read access than the default `GITHUB_TOKEN`.

### `ghas-campaign-bot.yml`

This bot turns the raw GHAS alert queue into a remediation-planning surface instead of a passive dashboard.

It now:

- groups open code scanning alerts by severity and age,
- highlights CodeQL/Copilot Autofix candidate volume,
- tracks secret-scanning age buckets and push-protection bypass follow-up,
- records repository security-configuration context when the API exposes it,
- opens a date-scoped `🧭 GHAS campaign planner (...)` issue.

### `security-configuration-audit-bot.yml`

This bot gives the repo a monthly control loop for newer GHAS operating-model features that are easy to forget once the initial setup is done.

It now:

- audits whether the expected GHAS workflows are present in the repo,
- verifies local supporting config files such as `dependabot.yml` and `codeql-config.yml`,
- queries the repository's attached code security configuration when available,
- snapshots open alert counts across code scanning, secret scanning, and Dependabot,
- opens a date-scoped `🧱 GHAS configuration audit (...)` issue.

### `ghas-alert-sla-bot.yml`

This bot adds an explicit age-based operating contract to the GHAS queue so stale findings cannot sit in the Security tab indefinitely without an owner.

It now:

- counts 7+, 14+, and 30+ day backlog slices across **code scanning**, **Dependabot**, and **secret scanning**,
- highlights 14+ day **high-severity** code/dependency findings,
- tracks **push-protection bypass** secret alerts that should be treated as same-week work,
- groups older CodeQL findings by rule so maintainers can batch-fix them instead of triaging one-by-one,
- opens a date-scoped `⏱️ GHAS alert SLA tracker (...)` issue.

### `secret-protection-review-bot.yml`

This bot adds a focused control loop for the newer GHAS secret-protection settings that are easy to enable once and then forget.

It now:

- reviews the open **secret scanning** backlog together with **push-protection bypass** follow-up volume,
- audits repository-level secret-protection settings such as **push protection**, **delegated bypass**, **delegated alert dismissal**, **validity checks**, **generic secrets**, and **non-provider patterns**,
- highlights the most common open secret types for faster triage,
- opens a date-scoped `🔑 Secret protection review (...)` issue.

### `ghas-metrics-export-bot.yml`

This bot turns GHAS operations into reusable evidence instead of ephemeral issue text.

It now:

- exports `build/ghas-metrics.json` as a workflow artifact,
- captures alert totals, age buckets, and severity distributions for **code scanning**, **Dependabot**, and **secret scanning**,
- records workflow freshness for the repo's GHAS automation surface,
- opens a date-scoped `📊 GHAS metrics snapshot (...)` issue,
- gives dashboards, weekly reviews, and future evidence packs a machine-readable GHAS baseline.

### `ghas-codeql-hotspots-bot.yml`

This bot gives the repo a CodeQL-first remediation lane instead of treating the code-scanning queue as a flat list.

It now:

- groups open **code scanning** alerts by **rule**, **tool**, and **file/path**,
- highlights 14+ and 30+ day hotspots so older findings are easier to batch-fix,
- exports `build/ghas-codeql-hotspots.json` for follow-up automation or dashboard reuse,
- opens a date-scoped `🧪 GHAS CodeQL hotspots (...)` issue.

### `repo-optimization-bot.yml`

This bot turns the repo's own umbrella-intelligence surfaces into a recurring enhancement and refactor control loop.

It now:

- runs `sdetkit kits optimize` and `sdetkit kits expand` with the repo's automation/GHAS goal,
- snapshots the `github_automation_check` maintenance signal beside those results,
- publishes a single issue with top feature candidates, GHAS update tracks, search missions, rollout tracks, and innovation opportunities,
- uploads reusable JSON artifacts for future roadmap, dashboard, or AgentOS consumption.

### `workflow-governance-bot.yml`

This bot adds a repo-wide automation hardening loop beyond GHAS-specific alert triage.

It now:

- audits every workflow for a top-level **permissions** block,
- flags reusable actions that are not pinned to a full commit SHA,
- flags scheduled workflows that are missing `workflow_dispatch` manual recovery,
- exports `build/workflow-governance-audit.json` for deterministic review,
- opens a date-scoped `🧾 Workflow governance audit (...)` issue.

### `dependency-radar-bot.yml`

This bot turns the repo's existing `upgrade-audit` intelligence into a scheduled maintenance surface.

It now:

- generates `build/dependency-radar.json`,
- creates a markdown summary with the hottest packages and validation lanes,
- builds a **runtime fast-follow watchlist** for hot-path runtime dependencies,
- uploads those artifacts to Actions,
- opens a date-scoped `📡 Dependency radar + runtime watchlist (...)` issue.

### `docs-experience-bot.yml`

This bot turns the docs site into a first-class maintenance lane instead of something maintainers only notice after navigation drift has accumulated.

It now:

- audits MkDocs navigation coverage against the actual `docs/` tree,
- highlights missing nav targets and high-value orphan docs that are outside the primary user journeys,
- checks that flagship entrypoint pages stay both present and visible in the main nav,
- records docs-search posture such as search suggest/highlight/share and instant navigation support,
- opens a date-scoped `📚 Docs experience radar (...)` issue,
- exports `build/docs-experience-radar.json` for dashboards, docs cleanup planning, or later AgentOS consumption.

### `release-readiness-radar-bot.yml`

This bot gives the repo a recurring release-ops review lane so publishing posture is not reconstructed manually right before a release.

It now:

- runs `python -m sdetkit doctor --format json` and captures the result as part of the release snapshot,
- reviews the presence of core release workflows such as `release.yml`, `pages.yml`, `versioning.yml`, and `docs-link-check.yml`,
- audits key release trust assets including `CHANGELOG.md`, `ROADMAP.md`, `RELEASE.md`, and the public release docs,
- reuses the GitHub automation maintenance check to highlight any required workflow/config gaps,
- opens a date-scoped `🚀 Release readiness radar (...)` issue,
- uploads `build/release-readiness-radar.json` plus the raw doctor/maintenance payloads as workflow artifacts.

### `worker-alignment-bot.yml`

This bot turns the worker layer into a first-class operating lane instead of leaving the templates as individual commands maintainers have to remember.

It now:

- runs `dependency-radar-worker`, `docs-search-radar`, `release-readiness-worker`, and `worker-alignment-radar` on a weekly cadence,
- uploads both the per-worker run records and the template output directories as reusable artifacts,
- opens a date-scoped `🤖 Worker alignment radar (...)` issue,
- keeps the worker surface aligned with dependency, docs, release, and automation-review loops.

## Recommended weekly maintainer flow

1. Open the latest **GHAS digest** issue.
2. Open the latest **GHAS campaign planner** issue and group any 14+ day backlog into a focused remediation lane.
3. Open the latest **GHAS alert SLA tracker** issue and convert every 14+ day breach into an owned issue or PR.
4. Review the **GHAS metrics snapshot** artifact before reporting progress or trend direction.
5. Review the **GHAS CodeQL hotspots** issue and batch the top rule or top file into one remediation lane.
6. Review the **secret protection review** issue and clear any push-protection bypass or delegated-bypass follow-up.
7. Clear or triage high-severity security findings first.
8. Open the latest **dependency radar** issue.
9. Open the latest **repo optimization control loop** issue and pick one `now` candidate or search mission.
10. Open the latest **docs experience radar** issue and fold the highest-value orphan docs or missing flagship links back into the canonical journeys.
11. Open the latest **release readiness radar** issue before a publish window or docs release push.
12. Open the latest **worker alignment radar** issue and refresh any stale worker/template lanes before they drift from the base automation surface.
13. Review the monthly **workflow governance audit** issue and close any pinning/permissions drift.
14. Record implementation follow-up in `docs/roadmap.md` and the weekly maintenance issue.

## Optional local dry runs

You can dry-run the same intelligence locally before relying on the bots:

```bash
python -m sdetkit intelligence upgrade-audit --format json --used-in-repo-only --top 10
python -m sdetkit intelligence upgrade-audit --impact-area runtime-core --repo-usage-tier hot-path --format md
python -m sdetkit kits optimize --goal "add more helpful automation bots and GitHub Advanced Security coverage" --format json
python -m sdetkit kits expand --goal "add more helpful automation bots and GitHub Advanced Security coverage" --format json
python -m sdetkit maintenance --include-check github_automation_check --format md
python -m sdetkit maintenance --include-check github_automation_check --format json | jq '.checks.github_automation_check.details.ghas_update_tracks'
python -m sdetkit agent templates run dependency-radar-worker
python -m sdetkit agent templates run worker-alignment-radar
```

## What this unlocks for the repo

These bots make the repo more than a set of commands; they turn it into a continuous maintenance system with:

- **better GHAS visibility**,
- **campaign-oriented GHAS backlog planning**,
- **age-based GHAS SLA enforcement**,
- **machine-readable GHAS metrics snapshots for dashboards and audits**,
- **CodeQL hotspot batching instead of one-alert-at-a-time triage**,
- **coverage checks for newer GHAS operating-model features**,
- **workflow-governance audits for permissions, SHA pinning, and manual recovery**,
- **scheduled dependency prioritization**,
- **a docs information-architecture control loop instead of ad hoc nav cleanup**,
- **a recurring release-ops radar for trust-asset and workflow freshness**,
- **a worker-alignment control loop that keeps template automation synchronized with the repo's strongest maintenance lanes**,
- **clearer issue-driven follow-up**,
- **smaller validation loops for upgrades and refactors**,
- **less hidden drift between security posture and maintenance work**.
