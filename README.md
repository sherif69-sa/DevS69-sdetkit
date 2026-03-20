# DevS69 SDETKit

DevS69 SDETKit is a unified SDET platform for:

1. **release confidence**
2. **test intelligence**
3. **integration assurance**
4. **failure forensics**

It turns CI and test signals into deterministic contracts, machine-readable artifacts, and clear go/no-go guidance.

## Umbrella kits (primary surface)

- **Release Confidence Kit** — `sdetkit release ...`
- **Test Intelligence Kit** — `sdetkit intelligence ...`
- **Integration Assurance Kit** — `sdetkit integration ...`
- **Failure Forensics Kit** — `sdetkit forensics ...`
- **Catalog** — `sdetkit kits list` / `sdetkit kits describe <kit>`

## Choose your SDET lane fast

- **Release confidence**: use when you need go/no-go readiness, repo health signals, and approval evidence.
- **Test intelligence**: use when you need smarter triage for flakes, failure clustering, impact analysis, or reproducible env capture.
- **Integration assurance**: use when you need stronger service-profile checks, environment readiness validation, and topology-aware contracts.
- **Failure forensics**: use when you need run-to-run diffs, repro bundles, and escalation-ready evidence packs.

For a fuller capability map, run:

```bash
python -m sdetkit kits list
python -m sdetkit kits describe release
python -m sdetkit kits describe intelligence
python -m sdetkit kits describe integration
python -m sdetkit kits describe forensics
python -m sdetkit kits search topology
python -m sdetkit kits blueprint --goal "agentized release upgrade search"
python -m sdetkit kits optimize --goal "upgrade umbrella architecture with agentos optimization"
python -m sdetkit kits expand --goal "upgrade umbrella architecture with agentos optimization"
python -m sdetkit kits radar --repo-usage-tier hot-path --format json
python -m sdetkit kits route-map httpx --repo-usage-tier hot-path --format json
python -m sdetkit intelligence upgrade-audit --format json --top 5
python -m sdetkit maintenance --include-check github_automation_check --format md
```

## Contributor quickstart (90 seconds)

If you want the fastest path from curiosity to contribution, run this trio:

```bash
python -m sdetkit onboarding --journey fast-start --format markdown
python -m sdetkit first-contribution --format markdown --strict
python -m sdetkit onboarding --journey first-pr --role sdet --format markdown
```

These commands give a new contributor three things immediately:

- a role-aware entrypoint instead of a generic wall of commands,
- a first-PR checklist that can be validated locally,
- and a curated command journey that turns the repo into an obvious place to start.

## Why contributors can move fast here

This repo now exposes a contributor launchpad instead of expecting newcomers to reverse-engineer the workflow:

```bash
python -m sdetkit first-contribution --format markdown --strict
python -m sdetkit first-contribution --profile docs-polish --format markdown
python -m sdetkit first-contribution --profile test-hardening --format markdown
python -m sdetkit first-contribution --profile automation-upgrade --format markdown
```

The launchpad checks that contributor trust assets are present, highlights concrete starter profiles, and points people toward realistic labels like `good first issue`, `documentation`, and `tests`.

If you are evaluating the project as a potential contributor, this makes the repo feel maintained, navigable, and ready for real work rather than just feature demos.

## Hero commands

```bash
python -m sdetkit kits list
python -m sdetkit release gate release
python -m sdetkit intelligence failure-fingerprint --failures examples/kits/intelligence/failures.json
python -m sdetkit integration check --profile examples/kits/integration/profile.json
python -m sdetkit integration topology-check --profile examples/kits/integration/heterogeneous-topology.json
# validates service owners, dependency edges, mocked platform coverage, deployments, telemetry, and data resilience
bash premium-gate.sh --mode full
# premium gate now emits .sdetkit/out/integration-topology.json as a first-class operational artifact
# head-5 also auto-runs repo-safe remediation scripts unless you pass --no-auto-run-scripts
# and writes .sdetkit/out/premium-remediation-plan.json so PRs can review selected vs deferred fixes
python -m sdetkit.premium_gate_engine --out-dir .sdetkit/out --search doctor --format json
python -m sdetkit.premium_gate_engine --db-path .sdetkit/out/premium-insights.db --list-guidelines --search security
python -m sdetkit forensics compare --from examples/kits/forensics/run-a.json --to examples/kits/forensics/run-b.json --fail-on error
python -m sdetkit forensics bundle --run examples/kits/forensics/run-b.json --output build/repro.zip
python -m sdetkit continuous-upgrade-cycle9-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle10-closeout --format json --strict
python -m sdetkit continuous-upgrade-cycle11-closeout --format json --strict
```

## Upgrade planning (first step)

Run a dependency-manifest audit against PyPI to identify candidate upgrades, detect cross-file version drift, and prioritize the highest-signal upgrade gaps. The audit now surfaces the repo baseline version, Python-policy-aware compatible targets, estimated version-gap size (major/minor/patch), release recency, release-freshness buckets, an ordered risk score, recommended maintenance lanes, repo impact areas, observed repo-usage tiers derived from imports across `src/` and `tests/`, validation command suggestions, group/source rollups, manifest actions, suggested target versions, and floor-and-lock baseline detection for repos that intentionally mix flexible ranges with tested pins. It also follows nested `-r` / `--requirement` includes so split requirement stacks are audited as a single upgrade surface. You can invoke it from either the standalone script or the primary Intelligence kit surface, filter the results down to the hottest dependency groups, manifest sources, repo-usage tiers, repo impact areas, or release-age windows, and fail CI at a chosen signal threshold:

```bash
make upgrade-audit
python -m sdetkit intelligence upgrade-audit --format json --top 5
python -m sdetkit intelligence upgrade-audit --include-prereleases --package httpx
python -m sdetkit intelligence upgrade-audit --format md --offline
python -m sdetkit intelligence upgrade-audit --outdated-only --package "http*"
python -m sdetkit intelligence upgrade-audit --used-in-repo-only --repo-usage-tier hot-path --format md
python -m sdetkit intelligence upgrade-audit --query runtime-core --query "next maintenance"
python -m sdetkit intelligence upgrade-audit --manifest-action stage-upgrade --top 10
python -m sdetkit intelligence upgrade-audit --validation-command "make docs-build"
python -m sdetkit intelligence upgrade-audit --group default --source pyproject.toml --format md
python scripts/upgrade_audit.py --format json > build/upgrade-audit.json
python scripts/upgrade_audit.py --fail-on high
python scripts/upgrade_audit.py --cache-ttl-hours 6 --max-workers 12
python scripts/upgrade_audit.py --offline --format md
python scripts/upgrade_audit.py --include-prereleases --signal high
python scripts/upgrade_audit.py --signal high --policy blocked --top 5
python scripts/upgrade_audit.py --impact-area runtime-core --format md
python scripts/upgrade_audit.py --max-release-age-days 14 --format md
python scripts/upgrade_audit.py --min-release-age-days 365 --outdated-only --format json
python scripts/upgrade_audit.py --repo-usage-tier active --used-in-repo-only --top 10
python scripts/upgrade_audit.py --metadata-source cache-stale --outdated-only
python scripts/upgrade_audit.py --group requirements --source requirements.txt --top 10
python -m sdetkit doctor --upgrade-audit --upgrade-audit-offline --format json
python -m sdetkit doctor --upgrade-audit --upgrade-audit-query quality --upgrade-audit-impact-area quality-tooling --upgrade-audit-top 5 --format md
python -m sdetkit doctor --upgrade-audit --upgrade-audit-manifest-action refresh-pin --upgrade-audit-top 3 --format json
python -m sdetkit doctor --upgrade-audit --upgrade-audit-package "http*" --upgrade-audit-source pyproject.toml --upgrade-audit-metadata-source cache-stale --format json
python -m sdetkit doctor --upgrade-audit --upgrade-audit-policy blocked --upgrade-audit-repo-usage-tier hot-path --upgrade-audit-used-in-repo-only --format md
python -m sdetkit doctor --upgrade-audit --upgrade-audit-max-release-age-days 14 --format md
bash quality.sh doctor
```

The audit also understands modern top-level `[dependency-groups]` declarations in `pyproject.toml`, including `{include-group = "..."}` expansion, so repos that have moved beyond legacy dev/test extras still get the same upgrade visibility and maintenance prioritization.

By default, the audit plans against stable releases first so dev/rc tags do not get promoted as normal maintenance work; use `--include-prereleases` when you explicitly want prerelease targets in the queue. When you already know the maintenance lane you want, filter directly by `--manifest-action` to isolate packages that need a pin refresh, floor raise, staged upgrade, or dedicated major-upgrade branch. Use `--query` when you want text search across package names, notes, repo-usage files, recommended lanes, and validation commands without pre-classifying the package first. Use `--max-release-age-days 14` to build a fast-follow watchlist for just-landed releases, or `--min-release-age-days 365 --outdated-only` to isolate older targets that have gone stale and deserve a deliberate cleanup pass.

When you want a surgically targeted maintenance queue, filter by `--validation-command` as well. That lets you answer questions like “show me only upgrades that roll into `make docs-build`” or “which candidates are covered by `bash quality.sh *` smoke validation” without scanning the whole report.

The doctor surface now carries those same upgrade-audit focus controls, so you can search and narrow dependency work without leaving the readiness report. In addition to query, impact-area, manifest-action, and repo-usage targeting, doctor now supports release-age slicing via `--upgrade-audit-min-release-age-days` and `--upgrade-audit-max-release-age-days`, plus `--upgrade-audit-used-in-repo-only` / `--upgrade-audit-outdated-only` for tighter maintenance slices. The readiness payload also exposes grouped action, dependency-group, manifest-source, and release-freshness summaries so CI and PR checks can explain whether the repo’s hottest maintenance lane is “fresh releases to validate” or “older targets to retire” without re-running the full audit. It also emits a quality summary block with pass/fail/skipped counts, pass rate, failing check IDs, and hint coverage so the readiness signal is easier to scan in CI, markdown, and JSON outputs.

The umbrella architecture is stronger too: `sdetkit kits search <query>` now ranks the best-fit kit for a problem statement, and `sdetkit kits blueprint --goal "..."` builds a cross-kit execution plan that explicitly layers AgentOS in as the control plane for recurring automation, history capture, and dashboard exports. That makes it easier to move from discovery to an opinionated release/test/integration/forensics operating model without stitching the surfaces together by hand.

The blueprint surface now goes further for umbrella-architecture upgrades: it emits explicit architecture layers, an operating model cadence, prioritized upgrade backlog items, and operating metrics so a team can move from "which kit should I start with?" to "how do I productize the whole umbrella with AgentOS on top?" without inventing its own framework first. When you want AgentOS to generate that operating plan directly, run:

```bash
python -m sdetkit kits blueprint --goal "upgrade umbrella architecture with agentos optimization"
python -m sdetkit kits optimize --goal "upgrade umbrella architecture with agentos optimization" --format json
bash quality.sh boost
python -m sdetkit agent run "umbrella architecture optimization blueprint" --approve
python -m sdetkit agent demo --scenario umbrella-upgrade-control-plane
```

The new optimize surface takes the blueprint one step further by inspecting the repo and aligning the umbrella kits with the operational lanes that actually keep the platform healthy: doctor, `quality.sh`, premium gate, integration topology, and AgentOS. It now also derives a manifest-aware upgrade inventory from the repo itself so the optimize payload can highlight hot-path dependencies, impact-area hotspots, dominant validation lanes, a concrete upgrade execution queue, and a small set of innovation opportunities that suggest what new repo capabilities would create the most leverage next. That gives you a single alignment payload showing which lanes are ready, which command should lead each domain, which operating sequence should be used, which search queries help continue the maintenance loop, the explicit doctor-to-quality promotion contract, the repo’s strongest dependency-maintenance focus, which new additions are worth productizing next, any missing domains, and which performance boosters are already available in the repo.

When you want that alignment to execute as a single repo-safe lane instead of a planning artifact, `bash quality.sh boost` now chains doctor, intelligent premium auto-fix, the fast gate, premium validation, topology proof, and an umbrella optimization summary into one command.

It now also emits an alignment score so the umbrella architecture has a single numeric readiness signal that can be tracked in CI, dashboards, and AgentOS history exports while the repo keeps getting upgraded.

When you want the repo to go beyond alignment planning and explicitly suggest what to add next, `sdetkit kits expand --goal "..."` turns those optimize signals into prioritized feature candidates, targeted search missions, and rollout tracks. That makes it easier to decide which new addition should land now, which should be queued next, and which search direction is most likely to unlock the next repo-wide upgrade.

Two of those additions are now implemented directly:

- `sdetkit kits radar`, which turns the dependency inventory into a dashboard-style maintenance radar with hotspot cards, watchlists, and recommended execution lanes,
- and `sdetkit kits route-map`, which turns the same inventory into a searchable package-to-validation route map.

Together they give refactors and upgrade work both a **macro view** of what is hottest in the repo and a **micro view** of the smallest safe validation command to run next.

The premium gate intelligence layer now goes further as well: it ranks remediation scripts by observed hotspot severity, can merge in repo-local smart fix scripts from `.sdetkit/premium-remediation-scripts.json`, emits a first-class `premium-remediation-plan.json` artifact, refreshes integration topology when contract drift is detected, and supports focused search across rendered findings plus learned guideline lookup from the premium insights database.

The security auto-remediation lane is stronger too: premium gate can now prioritize a built-in `security_fix_apply` smart script before baseline-aware security re-triage, and the security fixer now safely rewrites `shell=True` to `shell=False` alongside request timeout injection and `yaml.safe_load` upgrades for deterministic repo-safe cleanup.

To make those upgrade lanes reproducible in CI, the repo now pins the validated toolchain in `constraints-ci.txt` while leaving `pyproject.toml` flexible enough for package consumers.

## Sample artifacts

- `examples/kits/intelligence/*`
- `examples/kits/integration/profile.json`
- `examples/kits/forensics/run-a.json`
- `examples/kits/forensics/run-b.json`

## Backward compatibility

Existing direct commands remain supported (`gate`, `doctor`, `security`, `repo`, `evidence`, `report`, `policy`, etc.).
They are preserved compatibility lanes; umbrella kits are the primary discovery and product entrypoint.

See `docs/migration-compatibility-note.md` for migration and experimental-status notes.

## Quality transformation

For the execution blueprint to reach a world-class quality bar across all bundled offerings, see `docs/world-class-quality-program.md`.
