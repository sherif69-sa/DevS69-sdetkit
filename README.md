# DevS69 SDETKit

DevS69 SDETKit is a release-confidence CLI: it gives engineering teams deterministic ship/no-ship decisions with machine-readable evidence, using one repeatable command path from local to CI.

**Primary outcome:** know if a change is ready to ship.

**Canonical first path:** `python -m sdetkit gate fast` → `python -m sdetkit gate release` → `python -m sdetkit doctor`.

## Product promise (30-second view)

SDETKit's primary user outcome is **shipping readiness confidence**: a team can decide go/no-go from explicit JSON evidence instead of ad hoc interpretation.

In plain terms: one clear product identity, one primary outcome, one canonical first path.

The primary path is always:

`python -m sdetkit gate fast` → `python -m sdetkit gate release` → `python -m sdetkit doctor`

Everything else (umbrella kits, utilities, historical/transition-era lanes) stays available, but is intentionally secondary to first-time adoption.

## Canonical first proof lane (start here)

Run this exact command path first in a brand-new repository (not this repo):

```bash
mkdir my-repo && cd my-repo
git init
python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

Expected first artifacts:

```text
build/
├── gate-fast.json
└── release-preflight.json
```

Inspect order:
1. `build/release-preflight.json` (`ok`, `failed_steps`, `profile`)
2. If `failed_steps` includes `gate_fast`, open `build/gate-fast.json` (`ok`, `failed_steps`, `profile`)
3. Use raw logs only after artifact triage

What success means:
- `release-preflight.json` has `ok: true`
- `gate-fast.json` has `ok: true`

What failure means:
- `ok: false` and/or non-empty `failed_steps` gives the first deterministic remediation target.
- A non-zero exit code with JSON artifacts present is still a trustworthy first run: inspect `failed_steps` instead of treating it as a hidden crash.

External first-run contract proof (automated):

```bash
python -m pytest -q tests/test_external_first_run_contract.py
```

This acceptance test creates a truly fresh temporary repo, installs SDETKit into a clean virtual environment, executes the canonical commands, and verifies artifact contracts.

```text
$ cd examples/adoption/real-repo
$ python -m sdetkit gate fast
exit 2  -> build/gate-fast.json: ok=false (fixture triage)
$ python -m sdetkit gate release
exit 2  -> build/release-preflight.json: ok=false (fixture triage)
$ python -m sdetkit doctor
exit 0  -> build/doctor.json: ok=true
```

Real fixture-oriented canonical flow; any failing gate result shown here is expected triage for the adoption fixture, not a product failure.

Context: [`docs/real-repo-adoption.md`](docs/real-repo-adoption.md)

## Canonical local-to-CI journey

## Top-tier reporting sample pipeline

Run the end-to-end seeded reporting flow (portfolio scorecard -> KPI snapshot -> contract checks -> bundle promotion):

```bash
make top-tier-reporting
```

Optional date/window overrides:

```bash
make top-tier-reporting DATE_TAG=2026-04-17 WINDOW_START=2026-04-11 WINDOW_END=2026-04-17 GENERATED_AT=2026-04-17T10:00:00Z
```

Primary artifacts produced under `docs/artifacts/`:

- `portfolio-scorecard-sample-<date>.json`
- `kpi-weekly-from-portfolio-<date>.json`
- `kpi-weekly-contract-check-<date>.json`
- `top-tier-contract-check-<date>.json`
- `top-tier-bundle-manifest-<date>.json`
- `top-tier-bundle-manifest-check-<date>.json`

See: [`docs/portfolio-reporting-recipe.md`](docs/portfolio-reporting-recipe.md) and [`docs/kpi-schema.md`](docs/kpi-schema.md).

## Production-readiness snapshot (investor/leadership brief)

Generate a deterministic readiness scorecard that summarizes governance, CI, quality, and release evidence surfaces.
The scorecard is content-aware (checks policy keywords and CI steps), so it is useful for real production triage:

```bash
python -m sdetkit readiness . --format text
python -m sdetkit readiness . --format json
```

Use this output in due-diligence decks, internal operating reviews, or go-to-production checkpoint meetings.
For repo targets, `sdetkit review` also publishes this snapshot into the review adaptive database (`adaptive_database.readiness_snapshot`).
Readiness output includes pass/miss scorecards and achievement tiers so reviewers can track quality progression over time.
Remediation recommendations are adaptive from scan evidence (lane/priority/rationale), not fixed static text.
The readiness snapshot also tracks test scenario capacity against a 250-scenario target for scale readiness planning.
For top-tier decisions, use `top_tier_ready` and `operational_tier` from readiness JSON.
Review adaptive database also includes large-scale analytics blocks (`quality_matrix`, `findings_analytics`, `action_analytics`, `scalability_posture`) to power richer dashboards.
For near-term launch operations, use `adaptive_database.release_readiness_contract` (`gate_decision`, blockers, next_24h_actions, next_72h_actions).
`sdetkit review` now also emits a standalone `adaptive-database.json` artifact for direct dashboard ingestion.
It also emits `release-readiness.json` and `release-readiness.md` for final launch call workflows.
Release readiness contract now includes `contract_id`, `generated_at_utc`, and `next_review_due_at_utc` for traceable handoffs.
It also includes a `trend` block so each run can compare decision/blocker movement vs the previous review.
`release_readiness_contract` now includes `risk_score`, `risk_band`, and `sla_review_hours` for release-room prioritization.
It also includes `blocker_catalog` for structured blocker triage (id/kind/severity/priority/next_action).
Blocker catalog now includes `owner_team` and per-blocker `response_sla_hours` for clear routing.
`release_readiness_contract.owner_summary` aggregates blocker workload by team for standup planning.
`release_readiness_contract.recommendation_engine` now provides structured now/next/watchlist + owner-route recommendations.
Review emits `recommendation-backlog.json` with scored recommendation backlog (`priority_index`) for execution sequencing.
`release_readiness_contract.agent_orchestration` now suggests which specialist agents/playbooks to run based on current blockers and risk.
Agent entries include `engine_signals` so orchestration decisions stay aligned with adaptive review outcomes.
Review also emits `review-contract-check.json` with machine-readable reviewer contract consistency checks.


- Canonical first proof: [`docs/blank-repo-to-value-60-seconds.md`](docs/blank-repo-to-value-60-seconds.md)
- Canonical real-repo fixture proof: [`docs/real-repo-adoption.md`](docs/real-repo-adoption.md)
- Canonical CI rollout path: [`docs/recommended-ci-flow.md`](docs/recommended-ci-flow.md)
- Canonical artifact decoder: [`docs/ci-artifact-walkthrough.md`](docs/ci-artifact-walkthrough.md)

## Review command format quick guide (operator adoption)

Use `sdetkit review` when you need one front-door decision pass over doctor/inspect/compare/project/history.

- Use `--format json` when you need the **full review payload** (deep debugging, custom analytics, or internal tooling that consumes all sections).
- Use `--format operator-json` when you need the **stable operator-facing integration contract** for CI jobs, dashboards, and operator automations.
- For operator integrations, prefer `operator-json` as the long-lived parsing surface.

Short deterministic examples:

```bash
python -m sdetkit review . --no-workspace --format json
python -m sdetkit review . --no-workspace --format operator-json
```

Practical machine-consumption examples:

```bash
# Full payload: inspect status + top-level counts for deeper triage scripts
python -m sdetkit review . --no-workspace --format json | jq '{status, severity, findings: (.top_matters | length)}'

# Stable operator contract: gate on operator-facing situation/actions fields
python -m sdetkit review . --no-workspace --format operator-json | jq '{status: .situation.status, severity: .situation.severity, now_actions: (.actions.now | length)}'
```

## Who this is for / not for

**Best fit**
- Teams that want deterministic release decisions instead of ad hoc interpretation.
- Engineers who need machine-readable evidence for PR/release review.
- Repos standardizing the same release checks in local and CI runs.

**Probably not a fit (yet)**
- Very low-risk repos that do not need structured release evidence.
- Teams that only want raw tool invocations with fully custom orchestration.

## Start here (canonical first path)

- Install (canonical): [`docs/install.md`](docs/install.md)
- Container runtime adoption: [`docs/container-runtime.md`](docs/container-runtime.md)
- Blank repo proof in 60 seconds (recommended first run): [`docs/blank-repo-to-value-60-seconds.md`](docs/blank-repo-to-value-60-seconds.md)
- Guided run (same canonical path): [`docs/ready-to-use.md`](docs/ready-to-use.md)
- Release-confidence model (why this product exists): [`docs/release-confidence.md`](docs/release-confidence.md)
- Root CLI grouping and canonical path view: `python -m sdetkit --help`
- Machine-readable public command contract: [`src/sdetkit/public_command_surface.json`](src/sdetkit/public_command_surface.json)
- Stability levels (policy boundary): [`docs/stability-levels.md`](docs/stability-levels.md) — understand what is stable vs advanced vs experimental
- Before/after evidence behavior: [`docs/before-after-evidence-example.md`](docs/before-after-evidence-example.md)
- Real evidence artifacts from this repo: [`docs/evidence-showcase.md`](docs/evidence-showcase.md)

## Secondary surfaces (after canonical confidence path)

These remain available and supported after the core release-confidence lane is trusted, but they are intentionally not the front-door recommendation.

### Extended repo lanes

```bash
make bootstrap
bash quality.sh ci
python -m sdetkit kits list
python -m sdetkit legacy list
python -m sdetkit legacy <historical-command>
python -m sdetkit --help --show-hidden
```

### Repo health snapshot

```bash
python -m pip install -r requirements-test.txt
# tests require Python >= 3.11
PYTHONPATH=src python -m sdetkit.test_bootstrap_contract --strict
PYTHONPATH=src python -m sdetkit.test_bootstrap_validate --strict
# optional CI-style evidence outputs:
./ci.sh quick --artifact-dir .sdetkit/out
make merge-ready
PYTHONPATH=src pytest -q
bash quality.sh cov
ruff check .
mutmut results
```

For a focused preflight playbook (checks, artifact outputs, exit codes), see [`docs/test-bootstrap.md`](docs/test-bootstrap.md).

### Coverage hardening migration (staged)

- **Previous default:** `bash quality.sh cov` used `COV_FAIL_UNDER=80` when unset.
- **New default (effective now):** `bash quality.sh cov` uses `COV_MODE=standard` (fail-under `85`).
- **Temporary compatibility override:** `COV_FAIL_UNDER=80 bash quality.sh cov` (or `COV_MODE=legacy bash quality.sh cov`).
- **Stricter enforcement target:** use `COV_MODE=strict` (fail-under `95`) for merge/release truth lanes by **July 1, 2026**.

### Project layout

```text
src/sdetkit/   # product code + CLI
tests/         # automated tests
docs/          # user and maintainer docs
examples/      # runnable examples
scripts/       # repo helper scripts
.sdetkit/      # local generated outputs
artifacts/     # generated evidence packs
```

## Documentation and references

- Docs hub: [`docs/index.md`](docs/index.md)
- Architecture quick map for contributors: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Release process: [`RELEASE.md`](RELEASE.md)
- Git workflow (branch tracking + ahead/behind): [`docs/git-workflow.md`](docs/git-workflow.md)
- Enterprise readiness audit: [`docs/enterprise-readiness-audit-2026-04.md`](docs/enterprise-readiness-audit-2026-04.md)

### Historical and transition-era references (secondary)

- Compare against ad hoc workflows: [`docs/sdetkit-vs-ad-hoc.md`](docs/sdetkit-vs-ad-hoc.md)
- Repo hygiene boundaries: [`docs/repo-cleanup-plan.md`](docs/repo-cleanup-plan.md)
- Ongoing repo status view: [`docs/repo-health-dashboard.md`](docs/repo-health-dashboard.md)
- Historical archive index: [`docs/archive/index.md`](docs/archive/index.md)
