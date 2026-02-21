# CLI

## kv

Reads key=value lines (stdin, --text, or --path) and prints JSON.

Examples:

- `sdetkit kv --text "a=1\nb=two"`
- `echo -e "a=1\nb=two" | sdetkit kv`
- `kvcli --help`

## apiget

Fetch JSON from a URL with retries, pagination, and trace helpers.

Examples:

- `sdetkit apiget https://example.com/api --expect dict`
- `sdetkit apiget https://example.com/items --expect list --paginate --max-pages 50`
- `sdetkit apiget https://example.com/items --expect list --retries 3 --retry-429 --timeout 2`
- `sdetkit apiget https://example.com/items --expect any --trace-header X-Request-ID --request-id abc-123`

## doctor

Repo health checks and diagnostics.

Examples:

- `sdetkit doctor --ascii`
- `sdetkit doctor --all`
- `sdetkit doctor --all --json`
- `sdetkit doctor --dev --ci --deps --clean-tree --pr`

See: doctor.md

## onboarding

Renders Day 1 role-based paths plus Day 5 platform setup snippets.

Examples:

- `sdetkit onboarding --format text`
- `sdetkit onboarding --role platform --format markdown`
- `sdetkit onboarding --platform all --format markdown --output docs/artifacts/day5-platform-onboarding-sample.md`
- `sdetkit onboarding --platform windows --format text`

Useful flags: `--role`, `--platform`, `--format`, `--output`. JSON output preserves role keys and adds `day5_platform_setup` for platform snippets.

See: day-1-ultra-upgrade-report.md and day-5-ultra-upgrade-report.md


## demo

Renders a Day 2 copy/paste walkthrough for fast product demos.

Examples:

- `sdetkit demo --execute --format text`
- `sdetkit demo --execute --format markdown --output docs/artifacts/day2-demo-sample.md`
- `sdetkit demo --format json`

Useful flags: `--execute`, `--timeout-seconds`, `--fail-fast`, `--target-seconds`.

See: day-2-ultra-upgrade-report.md


## proof

Renders a Day 3 proof pack for doctor, repo audit, and security evidence capture.

Examples:

- `sdetkit proof --format text`
- `sdetkit proof --execute --strict --format text`
- `sdetkit proof --execute --strict --format markdown --output docs/artifacts/day3-proof-sample.md`

Useful flags: `--execute`, `--timeout-seconds`, `--strict`.

See: day-3-ultra-upgrade-report.md


## docs-qa

Runs Day 6 conversion QA against markdown links and heading anchors in `README.md` and `docs/`, including reference-style links and duplicate-heading anchors.

Examples:

- `sdetkit docs-qa --format text`
- `sdetkit docs-qa --format json`
- `sdetkit docs-qa --format markdown --output docs/artifacts/day6-conversion-qa-sample.md`

Useful flags: `--root`, `--week`, `--signals-file`, `--previous-signals-file`, `--emit-pack-dir`, `--strict`, `--format`, `--output`.

See: day-6-ultra-upgrade-report.md



## weekly-review

Builds weekly review output (Day 7/week 1, Day 14/week 2, and Day 21/week 3) with shipped upgrades, KPI movement, growth signals, and blocker-fix closeout data.

Examples:

- `sdetkit weekly-review --week 1 --format text`
- `sdetkit weekly-review --week 2 --format json --signals-file docs/artifacts/day14-growth-signals.json --previous-signals-file docs/artifacts/day7-growth-signals.json`
- `sdetkit weekly-review --week 1 --format markdown --output docs/artifacts/day7-weekly-review-sample.md`
- `sdetkit weekly-review --week 2 --format markdown --signals-file docs/artifacts/day14-growth-signals.json --previous-signals-file docs/artifacts/day7-growth-signals.json --output docs/artifacts/day14-weekly-review-sample.md`
- `sdetkit weekly-review --week 2 --emit-pack-dir docs/artifacts/day14-weekly-pack --format json --strict`
- `sdetkit weekly-review --week 3 --format json --signals-file docs/artifacts/day21-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --strict`
- `sdetkit weekly-review --week 3 --format markdown --signals-file docs/artifacts/day21-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --output docs/artifacts/day21-weekly-review-sample.md`
- `sdetkit weekly-review --week 3 --emit-pack-dir docs/artifacts/day21-weekly-pack --signals-file docs/artifacts/day21-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --format json --strict`

Useful flags: `--root`, `--week`, `--signals-file`, `--previous-signals-file`, `--emit-pack-dir`, `--strict`, `--format`, `--output`.

`--emit-pack-dir` writes week-specific closeout files: Day 14 checklist/action plan for week 2, and Day 21 checklist/scorecard/contributor-response/narrative brief for week 3.

See: day-7-ultra-upgrade-report.md and day-21-ultra-upgrade-report.md


## contributor-funnel

Builds Day 8 contributor funnel output with 10 curated good-first-issue tasks and explicit acceptance criteria.

Examples:

- `sdetkit contributor-funnel --format text --strict`
- `sdetkit contributor-funnel --format json`
- `sdetkit contributor-funnel --format markdown --output docs/artifacts/day8-good-first-issues-sample.md`
- `sdetkit contributor-funnel --area docs --issue-pack-dir docs/artifacts/day8-issue-pack`

Useful flags: `--format`, `--output`, `--area`, `--issue-pack-dir`, `--strict`.

`--strict` validates the full Day 8 backlog contract (10 issues, each with at least 3 acceptance criteria) and returns non-zero if it drifts.

See: day-8-ultra-upgrade-report.md

## triage-templates

Builds Day 9 contribution-template health output to harden issue/PR intake and speed maintainer triage.

Examples:

- `sdetkit triage-templates --format text --strict`
- `sdetkit triage-templates --format json`
- `sdetkit triage-templates --write-defaults --format json --strict`
- `sdetkit triage-templates --format markdown --output docs/artifacts/day9-triage-templates-sample.md`

Useful flags: `--root`, `--format`, `--output`, `--strict`, `--write-defaults`, `--emit-pack-dir`, `--execute`, `--evidence-dir`, `--timeout-sec`.

`--strict` returns non-zero if required Day 9 triage checks are missing from bug/feature/PR templates or `.github/ISSUE_TEMPLATE/config.yml`.

`--write-defaults` writes a hardened baseline for bug/feature/PR/config templates, then re-runs validation in the same command.

See: day-9-ultra-upgrade-report.md

## first-contribution

Builds Day 10 first-contribution checklist output and validates that `CONTRIBUTING.md` contains the guided path from fork to PR.

Examples:

- `sdetkit first-contribution --format text --strict`
- `sdetkit first-contribution --format json`
- `sdetkit first-contribution --write-defaults --format json --strict`
- `sdetkit first-contribution --format markdown --output docs/artifacts/day10-first-contribution-checklist-sample.md`

Useful flags: `--root`, `--format`, `--output`, `--strict`, `--write-defaults`, `--emit-pack-dir`, `--execute`, `--evidence-dir`, `--timeout-sec`.

`--strict` returns non-zero if required Day 10 checklist content or required command snippets are missing from `CONTRIBUTING.md`.

`--write-defaults` writes a default Day 10 checklist block to `CONTRIBUTING.md` if missing, then re-validates in the same run.

See: day-10-ultra-upgrade-report.md

## docs-nav

Builds Day 11 docs-navigation status and validates one-click journey links from `docs/index.md`.

Examples:

- `sdetkit docs-nav --format text --strict`
- `sdetkit docs-nav --format json`
- `sdetkit docs-nav --write-defaults --format json --strict`
- `sdetkit docs-nav --format markdown --output docs/artifacts/day11-docs-navigation-sample.md`

Useful flags: `--root`, `--format`, `--output`, `--strict`, `--write-defaults`, `--emit-pack-dir`, `--execute`, `--evidence-dir`, `--timeout-sec`.

`--strict` returns non-zero if required Day 11 journey links/content are missing from `docs/index.md`.

`--write-defaults` repairs the quick-jump nav block, restores the Day 11 top-journey section when missing, and then validates again.

See: day-11-ultra-upgrade-report.md

## startup-use-case

Builds Day 12 startup/small-team landing-page status and validates required workflow sections and runnable command sequence.

Examples:

- `sdetkit startup-use-case --format text --strict`
- `sdetkit startup-use-case --format json`
- `sdetkit startup-use-case --write-defaults --format json --strict`
- `sdetkit startup-use-case --format markdown --output docs/artifacts/day12-startup-use-case-sample.md`
- `sdetkit startup-use-case --emit-pack-dir docs/artifacts/day12-startup-pack --format json --strict`

Useful flags: `--root`, `--format`, `--output`, `--strict`, `--write-defaults`, `--emit-pack-dir`, `--execute`, `--evidence-dir`, `--timeout-sec`.

`--strict` returns non-zero if required Day 12 use-case sections or command snippets are missing from `docs/use-cases-startup-small-team.md`.

`--write-defaults` writes a hardened Day 12 startup workflow page if missing/incomplete, then validates again.

`--emit-pack-dir` writes a startup operating-pack bundle containing checklist, CI fast-lane recipe, and risk register files.

See: day-12-ultra-upgrade-report.md

## enterprise-use-case

Builds Day 13 enterprise/regulated landing-page status and validates required governance sections and compliance command sequence.

Examples:

- `sdetkit enterprise-use-case --format text --strict`
- `sdetkit enterprise-use-case --format json`
- `sdetkit enterprise-use-case --write-defaults --format json --strict`
- `sdetkit enterprise-use-case --format markdown --output docs/artifacts/day13-enterprise-use-case-sample.md`
- `sdetkit enterprise-use-case --emit-pack-dir docs/artifacts/day13-enterprise-pack --format json --strict`
- `sdetkit enterprise-use-case --execute --evidence-dir docs/artifacts/day13-enterprise-pack/evidence --format json --strict`

Useful flags: `--root`, `--format`, `--output`, `--strict`, `--write-defaults`, `--emit-pack-dir`, `--execute`, `--evidence-dir`, `--timeout-sec`.

`--strict` returns non-zero if required Day 13 use-case sections or command snippets are missing from `docs/use-cases-enterprise-regulated.md`.

`--write-defaults` writes a hardened Day 13 enterprise workflow page if missing/incomplete, then validates again.

`--emit-pack-dir` writes an enterprise operating-pack bundle containing checklist, CI compliance-lane recipe, and controls register files.

`--execute` runs the required Day 13 command chain and adds execution pass/fail details to output.

`--evidence-dir` writes `day13-execution-summary.json` plus per-command log files for audit handoff.

See: day-13-ultra-upgrade-report.md

## github-actions-quickstart

Builds Day 15 GitHub Actions quickstart status and validates required integration sections, workflow variants, and execution evidence workflow.

Examples:

- `sdetkit github-actions-quickstart --format text --strict`
- `sdetkit github-actions-quickstart --format json --variant strict --strict`
- `sdetkit github-actions-quickstart --write-defaults --format json --strict`
- `sdetkit github-actions-quickstart --format markdown --variant strict --output docs/artifacts/day15-github-actions-quickstart-sample.md`
- `sdetkit github-actions-quickstart --emit-pack-dir docs/artifacts/day15-github-pack --format json --strict`
- `sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/day15-github-pack/evidence --format json --strict`

Useful flags: `--root`, `--format`, `--output`, `--strict`, `--write-defaults`, `--emit-pack-dir`, `--variant`, `--execute`, `--evidence-dir`, `--timeout-sec`.

`--strict` returns non-zero if required Day 15 quickstart sections or command snippets are missing from `docs/integrations-github-actions-quickstart.md`.

`--write-defaults` writes a hardened Day 15 quickstart page if missing/incomplete, then validates again.

`--emit-pack-dir` writes a Day 15 integration pack containing checklist, minimal/strict/nightly workflows, distribution plan, and validation commands.

`--execute` runs Day 15 command chain and captures pass/fail output.

`--evidence-dir` writes `day15-execution-summary.json` plus per-command log files for CI incident triage and closeout handoff.

See: day-15-ultra-upgrade-report.md


## gitlab-ci-quickstart

Builds Day 16 GitLab CI quickstart status and validates required integration sections, pipeline variants, and execution evidence workflow.

Examples:

- `sdetkit gitlab-ci-quickstart --format text --strict`
- `sdetkit gitlab-ci-quickstart --format json --variant strict --strict`
- `sdetkit gitlab-ci-quickstart --write-defaults --format json --strict`
- `sdetkit gitlab-ci-quickstart --format markdown --variant strict --output docs/artifacts/day16-gitlab-ci-quickstart-sample.md`
- `sdetkit gitlab-ci-quickstart --emit-pack-dir docs/artifacts/day16-gitlab-pack --format json --strict`
- `sdetkit gitlab-ci-quickstart --variant strict --bootstrap-pipeline --pipeline-path .gitlab-ci.yml --format json --strict`
- `sdetkit gitlab-ci-quickstart --execute --evidence-dir docs/artifacts/day16-gitlab-pack/evidence --format json --strict`

Useful flags: `--root`, `--format`, `--output`, `--strict`, `--write-defaults`, `--emit-pack-dir`, `--variant`, `--bootstrap-pipeline`, `--pipeline-path`, `--execute`, `--evidence-dir`, `--timeout-sec`.

`--strict` returns non-zero if required Day 16 quickstart sections or command snippets are missing from `docs/integrations-gitlab-ci-quickstart.md`.

`--write-defaults` writes a hardened Day 16 quickstart page if missing/incomplete, then validates again.

`--emit-pack-dir` writes a Day 16 integration pack containing checklist, minimal/strict/nightly pipelines, distribution plan, and validation commands.

`--bootstrap-pipeline` writes the selected pipeline variant directly to `--pipeline-path` for copy/paste-free adoption.

`--execute` runs Day 16 command chain and captures pass/fail output.

`--evidence-dir` writes `day16-execution-summary.json` plus per-command log files for CI incident triage and closeout handoff.

See: day-16-ultra-upgrade-report.md

## quality-contribution-delta

Builds Day 17 quality + contribution week-over-week delta evidence from two signal files and weekly review KPIs.

Examples:

- `sdetkit quality-contribution-delta --current-signals-file docs/artifacts/day17-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --format text`
- `sdetkit quality-contribution-delta --current-signals-file docs/artifacts/day17-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --format json --strict`
- `sdetkit quality-contribution-delta --current-signals-file docs/artifacts/day17-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --min-traffic-delta 100 --min-stars-delta 5 --min-discussions-delta 2 --min-blocker-fixes-delta 1 --format json --strict`
- `sdetkit quality-contribution-delta --current-signals-file docs/artifacts/day17-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --format markdown --output docs/artifacts/day17-quality-contribution-delta-sample.md`
- `sdetkit quality-contribution-delta --current-signals-file docs/artifacts/day17-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --emit-pack-dir docs/artifacts/day17-delta-pack --format json --strict`

Useful flags: `--root`, `--current-signals-file`, `--previous-signals-file`, `--emit-pack-dir`, `--strict`, `--min-traffic-delta`, `--min-stars-delta`, `--min-discussions-delta`, `--min-blocker-fixes-delta`, `--format`, `--output`.

`--emit-pack-dir` writes a Day 17 evidence pack containing delta summary JSON, quality scorecard markdown, contribution action plan markdown, and a remediation checklist.

`--strict` returns non-zero when any strict delta gate fails (quality regression or contribution delta below minimum thresholds).

See: day-17-ultra-upgrade-report.md

## reliability-evidence-pack

Builds Day 18 reliability evidence by combining Day 15 GitHub execution logs, Day 16 GitLab execution logs, and Day 17 quality/contribution delta summary.

Examples:

- `sdetkit reliability-evidence-pack --format text`
- `sdetkit reliability-evidence-pack --format json --strict`
- `sdetkit reliability-evidence-pack --write-defaults --format json --strict`
- `sdetkit reliability-evidence-pack --emit-pack-dir docs/artifacts/day18-reliability-pack --format json --strict`
- `sdetkit reliability-evidence-pack --execute --evidence-dir docs/artifacts/day18-reliability-pack/evidence --format json --strict`
- `sdetkit reliability-evidence-pack --format markdown --output docs/artifacts/day18-reliability-evidence-pack-sample.md`

Useful flags: `--root`, `--day15-summary`, `--day16-summary`, `--day17-summary`, `--min-reliability-score`, `--write-defaults`, `--emit-pack-dir`, `--execute`, `--evidence-dir`, `--timeout-sec`, `--strict`, `--format`, `--output`.

`--write-defaults` writes a hardened Day 18 integration page if missing/incomplete, then validates it.

`--emit-pack-dir` writes a Day 18 pack containing reliability summary JSON, scorecard markdown, closeout checklist markdown, and a validation commands file.

`--execute` runs the Day 18 command chain and emits an execution summary plus per-command logs for closeout evidence.

`--strict` returns non-zero if Day 18 required docs sections/commands are missing, strict gates are not green across Day 15/16/17 inputs, or reliability score falls below `--min-reliability-score`.

See: day-18-ultra-upgrade-report.md

## patch

Deterministic, spec-driven file edits (official CLI command).

Examples:

- `sdetkit patch spec.json --check`
- `sdetkit patch spec.json --dry-run`
- `sdetkit patch spec.json --root /workspace/myrepo`
- `sdetkit patch spec.json --report-json patch-report.json`

`--root` defaults to the current Git repository root (when inside a repo) and falls back to the current working directory otherwise.

Exit codes: `0` success/no-op, `1` changes required in `--check`, `2` invalid/unsafe/error.

Safety limits include `--max-files`, `--max-bytes-per-file`, `--max-total-bytes-changed`, `--max-op-count`, and `--max-spec-bytes`.

Backward compatibility wrapper still works:

- `python tools/patch_harness.py spec.json --check`

See: patch-harness.md


## Security defaults

All CLI tools now default to safer behavior:

- Secret redaction is ON by default for printed HTTP request/response metadata (`--redact`, `--no-redact`, `--redact-keys KEY`).
- HTTP clients enforce explicit timeouts and allow only `http/https` schemes by default (`--allow-scheme`).
- Redirect behavior is explicit (`--follow-redirects` / `--no-follow-redirects`).
- TLS verification stays enabled by default; `--insecure` is opt-in and emits a warning.
- File outputs refuse unsafe paths and existing files unless explicitly forced (`--force`).

Tool-specific notes:

- `apiget`: supports redaction flags, scheme allowlist, secure timeout defaults, explicit redirects, and safe output writes.
- `cassette-get`: supports scheme allowlist, secure timeout defaults, explicit redirects, safe cassette writes, and `--force` for overwrites.
- `kv`: input parsing remains backward compatible for stdin, --text, and --path usage.
- `patch`: report output uses safe paths + atomic writes and requires `--force` to overwrite.
- `doctor`: returns `1` for failing checks, `0` for pass, while usage/runtime issues map to `2` in shared CLI wrappers.


## `repo`

- `sdetkit repo audit [PATH] [--profile default|enterprise] [--pack PACKS] [--org-pack PACK ...] [--format text|json|sarif] [--json-schema legacy|v1] [--output PATH] [--emit-run-record PATH] [--diff-against RUN.json] [--step-summary] [--config PATH] [--baseline PATH] [--update-baseline] [--exclude GLOB ...] [--disable-rule RULE_ID ...] [--fail-on none|warn|error] [--all-projects] [--fail-strategy overall|per-project] [--sort] [--changed-only] [--since-ref REF] [--include-untracked|--no-include-untracked] [--include-staged|--no-include-staged] [--require-git] [--cache-dir PATH] [--no-cache] [--cache-stats] [--jobs N] [--force]`
- `sdetkit repo audit ... [--ide vscode|generic] [--ide-output PATH] [--include-suppressed]`
- `sdetkit repo baseline create [PATH] [--output BASELINE.json] [--profile default|enterprise] [--exclude GLOB ...]`
- `sdetkit repo rules list [--profile default|enterprise] [--pack PACKS] [--org-pack PACK ...] [--json]`
- `sdetkit repo fix-audit [PATH] [--profile ...] [--pack PACKS] [--org-pack PACK ...] [--project NAME|--all-projects] [--dry-run|--apply] [--diff] [--patch OUT.patch] [--sort] [--changed-only] [--since-ref REF] [--include-untracked|--no-include-untracked] [--include-staged|--no-include-staged] [--require-git] [--cache-dir PATH] [--no-cache] [--cache-stats] [--jobs N] [--force]`
- `sdetkit repo pr-fix [PATH] [--profile ...] [--pack PACKS] [--project NAME|--all-projects] [--dry-run|--apply] [--branch BRANCH] [--force-branch] [--commit|--no-commit] [--base-ref REF] [--open-pr] [--repo OWNER/NAME] [--token-env GITHUB_TOKEN] [--title TITLE] [--body BODY|--body-file PATH] [--draft] [--labels a,b,c] [--changed-only] [--since-ref REF] [--include-untracked|--no-include-untracked] [--include-staged|--no-include-staged] [--require-git] [--cache-dir PATH] [--no-cache] [--cache-stats] [--jobs N]`
- `sdetkit repo baseline check [PATH] [--baseline BASELINE.json] [--fail-on none|warn|error] [--update] [--diff]`
- `sdetkit repo policy lint [PATH] [--config PATH] [--format text|json] [--fail-on none|warn|error]`
- `sdetkit repo policy export [PATH] [--config PATH] [--output FILE.json] [--include-expired]`
- `sdetkit repo check [PATH] [--format text|json|md] [--out PATH] [--fail-on LEVEL] [--min-score N]`
- `sdetkit repo ops [PATH] [--format text|json] [--output PATH] [--min-score N]`
- `sdetkit repo fix [PATH] [--check|--dry-run] [--diff] [--eol lf|crlf]`
- `sdetkit repo init [PATH] [--profile default|enterprise] [--dry-run] [--apply] [--force] [--diff]`
- Security-first defaults: safe paths, deterministic sorted outputs, and atomic writes.

Audit examples:

- `sdetkit repo audit`
- `sdetkit repo audit --format json --out repo-audit.json --force`
- `sdetkit repo ops --format json --output ops-report.json --force`
- `sdetkit repo baseline create .`
- `sdetkit repo baseline check . --diff`

Init examples:

- `sdetkit repo init` (safe dry-run default)
- `sdetkit repo init --diff`
- `sdetkit repo init --apply --profile enterprise`

See: repo-init.md and plugins-and-fix.md

See also: security-suite.md

See also: pr-automation.md

GitHub Action integration:

- Use `.github/actions/repo-audit` for CI summary + SARIF + JSON artifact workflows.
- See: github-action.md


## `report`

- `sdetkit report ingest RUN.json [--history-dir .sdetkit/audit-history] [--label LABEL]`
- `sdetkit report diff --from RUN.json --to RUN.json [--format text|json|md] [--fail-on none|warn|error] [--limit-new N]`
- `sdetkit report build [--history-dir .sdetkit/audit-history] [--output report.html] [--format html|md] [--since N]`

See: reporting-and-trends.md

- `sdetkit repo projects list [PATH] [--json] [--sort]`

## `dev`

- `sdetkit dev audit [PATH] [--mode changed-only|full] [--pack PACKS] [--profile default|enterprise]`
- `sdetkit dev fix [PATH] [--mode changed-only|full] [--pack PACKS] [--profile default|enterprise] [--diff] [--apply]`
- `sdetkit dev precommit install [PATH] [--profile ...] [--pack ...] [--mode changed-only|full] [--apply] [--dry-run] [--force] [--diff]`

See: ide-and-precommit.md

## `agent`

- `sdetkit agent init [--config PATH]`
- `sdetkit agent run <task> [--config PATH] [--approve] [--cache-dir PATH] [--no-cache]`
- `sdetkit agent doctor [--config PATH]`
- `sdetkit agent history [--limit N]`
- `sdetkit agent serve [--config PATH] [--host HOST] [--port N] [--telegram-simulation-mode] [--telegram-enable-outgoing] [--rate-limit-max-tokens N] [--rate-limit-refill-per-second N] [--tool-bridge-enabled] [--tool-bridge-allow TOOL ...] [--tool-bridge-command ARG ...]`
- `sdetkit agent templates list`
- `sdetkit agent templates show <id>`
- `sdetkit agent templates run <id> [--set key=value ...] [--output-dir DIR]`
- `sdetkit agent templates pack [--output FILE.tar]`
- `sdetkit agent templates run-all [--output-dir DIR]`

See: agentos-foundation.md, omnichannel-mcp-bridge.md, and automation-templates-engine.md


## CLI consistency notes

- Agent/report commands use shared option names where applicable: `--history-dir`, `--output`, `--format`, `--config`, `--cache-dir`, `--no-cache`, `--approve`, `--output-dir`, and `--set`.
- `--help` output includes default values for faster operator onboarding.
- Normal user errors are emitted as single-line messages (`agent error: ...`, `report error: ...`) without stack traces.


## release-readiness-board

Builds Day 19 release-readiness evidence by combining Day 18 reliability summary and Day 14 weekly KPI summary.

Examples:

- `sdetkit release-readiness-board --format text`
- `sdetkit release-readiness-board --format json --strict`
- `sdetkit release-readiness-board --write-defaults --format json --strict`
- `sdetkit release-readiness-board --emit-pack-dir docs/artifacts/day19-release-readiness-pack --format json --strict`
- `sdetkit release-readiness-board --execute --evidence-dir docs/artifacts/day19-release-readiness-pack/evidence --format json --strict`
- `sdetkit release-readiness-board --format markdown --output docs/artifacts/day19-release-readiness-board-sample.md`

Useful flags: `--root`, `--day18-summary`, `--day14-summary`, `--min-release-score`, `--write-defaults`, `--emit-pack-dir`, `--execute`, `--evidence-dir`, `--timeout-sec`, `--strict`, `--format`, `--output`.

`--write-defaults` writes a hardened Day 19 integration page if missing/incomplete, then validates it.

`--emit-pack-dir` writes a Day 19 pack containing summary JSON, scorecard markdown, closeout checklist markdown, and a validation commands file.

`--execute` runs the Day 19 command chain and emits an execution summary plus per-command logs for closeout evidence.

`--strict` returns non-zero if Day 19 required docs sections/commands are missing, strict gates are not green, or release score falls below `--min-release-score`.

## release-narrative

Builds Day 20 release storytelling from Day 19 release-readiness summary and changelog highlights.

Examples:

- `sdetkit release-narrative --format text`
- `sdetkit release-narrative --format json --strict`
- `sdetkit release-narrative --write-defaults --format json --strict`
- `sdetkit release-narrative --emit-pack-dir docs/artifacts/day20-release-narrative-pack --format json --strict`
- `sdetkit release-narrative --execute --evidence-dir docs/artifacts/day20-release-narrative-pack/evidence --format json --strict`
- `sdetkit release-narrative --format markdown --output docs/artifacts/day20-release-narrative-sample.md`

Useful flags: `--root`, `--day19-summary`, `--changelog`, `--min-release-score`, `--write-defaults`, `--emit-pack-dir`, `--execute`, `--evidence-dir`, `--timeout-sec`, `--strict`, `--format`, `--output`.

`--write-defaults` writes a hardened Day 20 integration page if missing/incomplete, then validates it.

`--emit-pack-dir` writes a Day 20 pack containing summary JSON, narrative markdown, audience blurbs, narrative channels, and validation commands.

`--execute` runs the Day 20 command chain and emits an execution summary plus per-command logs for closeout evidence.

`--strict` returns non-zero if Day 20 required docs sections/commands are missing, release posture is not ready, or release score falls below `--min-release-score`.

## trust-signal-upgrade

Builds Day 22 trust visibility posture from README badges, governance-policy discoverability links, and workflow/docs-index visibility checks.

Examples:

- `sdetkit trust-signal-upgrade --format text`
- `sdetkit trust-signal-upgrade --format json --strict`
- `sdetkit trust-signal-upgrade --write-defaults --format json --strict`
- `sdetkit trust-signal-upgrade --emit-pack-dir docs/artifacts/day22-trust-pack --format json --strict`
- `sdetkit trust-signal-upgrade --execute --evidence-dir docs/artifacts/day22-trust-pack/evidence --format json --strict`
- `sdetkit trust-signal-upgrade --format markdown --output docs/artifacts/day22-trust-signal-upgrade-sample.md`

Useful flags: `--root`, `--readme`, `--docs-index`, `--min-trust-score`, `--write-defaults`, `--emit-pack-dir`, `--execute`, `--evidence-dir`, `--timeout-sec`, `--strict`, `--format`, `--output`.

`--write-defaults` writes a hardened Day 22 integration page if missing/incomplete, then validates it.

`--emit-pack-dir` writes a Day 22 pack containing summary JSON, trust scorecard markdown, visibility checklist markdown, trust action plan, and a validation commands file.

`--execute` runs the Day 22 command chain and emits an execution summary plus per-command logs for closeout evidence.

`--strict` returns non-zero if Day 22 required docs sections/commands are missing, any critical trust checks fail, or trust score falls below `--min-trust-score`.

## faq-objections

Builds Day 23 objection-handling readiness from FAQ coverage, adoption clarity signals, and docs discoverability links.

Examples:

- `sdetkit faq-objections --format text`
- `sdetkit faq-objections --format json --strict`
- `sdetkit faq-objections --write-defaults --format json --strict`
- `sdetkit faq-objections --emit-pack-dir docs/artifacts/day23-faq-pack --format json --strict`
- `sdetkit faq-objections --execute --evidence-dir docs/artifacts/day23-faq-pack/evidence --format json --strict`
- `sdetkit faq-objections --format markdown --output docs/artifacts/day23-faq-objections-sample.md`

Useful flags: `--root`, `--readme`, `--docs-index`, `--docs-page`, `--min-faq-score`, `--write-defaults`, `--emit-pack-dir`, `--execute`, `--evidence-dir`, `--timeout-sec`, `--strict`, `--format`, `--output`.

`--write-defaults` writes a hardened Day 23 FAQ page if missing/incomplete, then validates it.

`--emit-pack-dir` writes a Day 23 pack containing summary JSON, FAQ scorecard markdown, objection-response matrix, adoption playbook, and validation commands.

`--execute` runs the Day 23 command chain and emits an execution summary for closeout evidence.

`--strict` returns non-zero if Day 23 required docs sections/commands are missing, critical objection checks fail, or FAQ score falls below `--min-faq-score`.

## community-activation

Builds Day 25 roadmap-voting and community-feedback readiness from docs contract completeness, discoverability links, and strategy alignment checks.

Examples:

- `sdetkit community-activation --format text`
- `sdetkit community-activation --format json --strict`
- `sdetkit community-activation --write-defaults --format json --strict`
- `sdetkit community-activation --emit-pack-dir docs/artifacts/day25-community-pack --format json --strict`
- `sdetkit community-activation --execute --evidence-dir docs/artifacts/day25-community-pack/evidence --format json --strict`

Useful flags: `--root`, `--readme`, `--docs-index`, `--top10`, `--write-defaults`, `--emit-pack-dir`, `--execute`, `--evidence-dir`, `--timeout-sec`, `--min-score`, `--strict`, `--format`.

`--write-defaults` writes a hardened Day 25 integration page if missing/incomplete, then validates it.

`--emit-pack-dir` writes a Day 25 pack containing summary JSON, activation scorecard markdown, roadmap-vote discussion template, feedback triage board, and validation commands.

`--execute` runs the Day 25 command chain and emits an execution summary for closeout evidence.

`--strict` returns non-zero if Day 25 required docs sections/commands are missing, critical checks fail, or activation score falls below `--min-score`.
