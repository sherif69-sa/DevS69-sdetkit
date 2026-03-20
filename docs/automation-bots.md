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
- **`ghas-review-bot.yml`** — creates the weekly GHAS digest issue with open-alert counts, workflow freshness, and follow-up prompts.
- **`ghas-campaign-bot.yml`** — creates a weekly GHAS campaign planner issue for Copilot Autofix-aware code scanning backlog slices, secret scanning age buckets, and push-protection follow-up.
- **`security-configuration-audit-bot.yml`** — creates a monthly GHAS configuration audit issue covering repo-local workflow coverage, code security configuration visibility, and dependency submission posture.
- **`dependency-review.yml`** — blocks pull requests that introduce vulnerable dependencies or denied license drift before they merge.

### Dependency and repo-maintenance bots

- **`dependency-auto-merge.yml`** — auto-merges safe Dependabot updates after checks pass.
- **`pre-commit-autoupdate.yml`** — refreshes pre-commit hook pins.
- **`dependency-radar-bot.yml`** — publishes a recurring dependency radar issue plus a runtime fast-follow watchlist.
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
3. Clear or triage high-severity security findings first.
4. Open the latest **dependency radar** issue.
5. Pick one upgrade candidate that already maps to a small validation command.
6. Record implementation follow-up in `docs/roadmap.md` and the weekly maintenance issue.

## Optional local dry runs

You can dry-run the same intelligence locally before relying on the bots:

```bash
python -m sdetkit intelligence upgrade-audit --format json --used-in-repo-only --top 10
python -m sdetkit intelligence upgrade-audit --impact-area runtime-core --repo-usage-tier hot-path --format md
python -m sdetkit kits optimize --goal "add more helpful automation bots and GitHub Advanced Security coverage" --format json
python -m sdetkit kits expand --goal "add more helpful automation bots and GitHub Advanced Security coverage" --format json
python -m sdetkit maintenance --include-check github_automation_check --format md
```

## What this unlocks for the repo

These bots make the repo more than a set of commands; they turn it into a continuous maintenance system with:

- **better GHAS visibility**,
- **campaign-oriented GHAS backlog planning**,
- **coverage checks for newer GHAS operating-model features**,
- **scheduled dependency prioritization**,
- **clearer issue-driven follow-up**,
- **smaller validation loops for upgrades and refactors**,
- **less hidden drift between security posture and maintenance work**.
