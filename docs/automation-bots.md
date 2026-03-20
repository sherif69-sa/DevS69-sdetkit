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
- **`repo-optimization-bot.yml`** — publishes a weekly repo-optimization control loop issue from `kits optimize`, `kits expand`, and the GitHub automation maintenance check.
- **`workflow-governance-bot.yml`** — publishes a monthly workflow-governance audit for permissions, SHA pinning, and manual recovery posture.
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
10. Review the monthly **workflow governance audit** issue and close any pinning/permissions drift.
11. Record implementation follow-up in `docs/roadmap.md` and the weekly maintenance issue.

## Optional local dry runs

You can dry-run the same intelligence locally before relying on the bots:

```bash
python -m sdetkit intelligence upgrade-audit --format json --used-in-repo-only --top 10
python -m sdetkit intelligence upgrade-audit --impact-area runtime-core --repo-usage-tier hot-path --format md
python -m sdetkit kits optimize --goal "add more helpful automation bots and GitHub Advanced Security coverage" --format json
python -m sdetkit kits expand --goal "add more helpful automation bots and GitHub Advanced Security coverage" --format json
python -m sdetkit maintenance --include-check github_automation_check --format md
python -m sdetkit maintenance --include-check github_automation_check --format json | jq '.checks.github_automation_check.details.ghas_update_tracks'
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
- **clearer issue-driven follow-up**,
- **smaller validation loops for upgrades and refactors**,
- **less hidden drift between security posture and maintenance work**.
