# DevS69 SDETKit

DevS69 SDETKit is a release-confidence CLI: it gives engineering teams deterministic ship/no-ship decisions with machine-readable evidence, using one repeatable command path from local to CI.

**Primary outcome:** know if a change is ready to ship.

## What this product is

SDETKit is a deterministic release-confidence layer for software teams that want one clear shipping decision (`ship` / `no-ship`) backed by JSON artifacts.

Instead of stitching together separate scripts and tools for every repo, teams run one canonical path and get machine-readable evidence they can use in pull requests, release reviews, and CI gates.

## Who it is for

**Best fit**
- Teams that want deterministic release decisions instead of ad hoc interpretation.
- Engineers who need machine-readable evidence for PR/release review.
- Repos standardizing the same release checks in local and CI runs.

**Probably not a fit (yet)**
- Very low-risk repos that do not need structured release evidence.
- Teams that only want raw tool invocations with fully custom orchestration.

## Canonical first path (run this first)

Canonical first path: `python -m sdetkit gate fast` -> `python -m sdetkit gate release` -> `python -m sdetkit doctor`.

Install the released package in an isolated environment (Python 3.11+):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install sdetkit==1.0.3
```

If you prefer an isolated global CLI install instead of a project venv, use `pipx install sdetkit==1.0.3`.

Then run the canonical path:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

## What artifacts appear

After the first path, expect:

```text
build/
├── gate-fast.json
└── release-preflight.json
```

Inspect in this order:
1. `build/release-preflight.json` (`ok`, `failed_steps`, `profile`)
2. If `failed_steps` includes `gate_fast`, inspect `build/gate-fast.json`
3. Use raw logs only after artifact triage

Decision rule:
- `ok: true` in both artifacts = ready to advance.
- `ok: false` and/or non-empty `failed_steps` = first deterministic remediation target.

## Where to go next

- Start here in docs: [`docs/start-here-5-minutes.md`](docs/start-here-5-minutes.md)
- Buyer-facing team overview: [`docs/why-sdetkit-for-teams.md`](docs/why-sdetkit-for-teams.md)
- Blank repo proof in 60 seconds: [`docs/blank-repo-to-value-60-seconds.md`](docs/blank-repo-to-value-60-seconds.md)
- CI rollout path: [`docs/recommended-ci-flow.md`](docs/recommended-ci-flow.md)
- Artifact decoder: [`docs/ci-artifact-walkthrough.md`](docs/ci-artifact-walkthrough.md)
- Team use cases: [`docs/use-cases.md`](docs/use-cases.md)
- Release confidence ROI: [`docs/release-confidence-roi.md`](docs/release-confidence-roi.md)
- Adoption-proof examples: [`docs/adoption-proof-examples.md`](docs/adoption-proof-examples.md)

## Canonical local-to-CI journey

The same first-path commands should run locally and in CI so teams make release decisions from consistent evidence contracts.

For a reproducible first-run acceptance proof in a fresh repo:

```bash
python -m pytest -q tests/test_external_first_run_contract.py
```

Context: [`docs/real-repo-adoption.md`](docs/real-repo-adoption.md)

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
- Support and issue routing: [`SUPPORT.md`](SUPPORT.md)
- Release process: [`RELEASE.md`](RELEASE.md)
- Git workflow (branch tracking + ahead/behind): [`docs/git-workflow.md`](docs/git-workflow.md)
- Enterprise readiness audit: [`docs/enterprise-readiness-audit-2026-04.md`](docs/enterprise-readiness-audit-2026-04.md)

### Historical and transition-era references (secondary)

- Compare against ad hoc workflows: [`docs/sdetkit-vs-ad-hoc.md`](docs/sdetkit-vs-ad-hoc.md)
- Repo hygiene boundaries: [`docs/repo-cleanup-plan.md`](docs/repo-cleanup-plan.md)
- Ongoing repo status view: [`docs/repo-health-dashboard.md`](docs/repo-health-dashboard.md)
- Historical archive index: [`docs/archive/index.md`](docs/archive/index.md)

## Top-tier reporting sample pipeline

Run `make top-tier-reporting` to generate a deterministic sample bundle and promotion artifacts.

- Recipe: [`docs/portfolio-reporting-recipe.md`](docs/portfolio-reporting-recipe.md)
- KPI schema: [`docs/kpi-schema.md`](docs/kpi-schema.md)
