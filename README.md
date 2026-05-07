<div align="center">
  <img src="docs/assets/logo-mark.svg" alt="DevS69 mark" width="68" />
  <h1>DevS69 SDETKit</h1>
  <p><strong>Deterministic release confidence for ship / no-ship decisions.</strong></p>
</div>

DevS69 SDETKit is a release-confidence CLI for deterministic ship/no-ship decisions with machine-readable evidence.

**Primary outcome:** know if a change is ready to ship.
**Runtime requirement:** Python 3.10+.

Canonical first path: `python -m sdetkit gate fast` -> `python -m sdetkit gate release` -> `python -m sdetkit doctor`.

## Start here

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install sdetkit==1.0.3

python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
```

Generated first-run artifacts:

```text
build/
├── gate-fast.json
├── release-preflight.json
└── doctor.json
```

## Decision contract

| Signal | Decision |
| --- | --- |
| `gate-fast.json.ok == true` and `release-preflight.json.ok == true` | ✅ SHIP |
| Any `ok: false` | ❌ NO-SHIP |
| `failed_steps` present in either artifact | ❌ NO-SHIP |

Canonical gate commands: `python -m sdetkit gate fast`, `python -m sdetkit gate release`, and `python -m sdetkit doctor`.

Secondary lanes cover review, investigation, quality, maintenance, and CI automation once the primary gate decision is stable. Investigation/reporting/planning lanes are diagnostic-only by default; repository mutation requires explicit guarded policy and PR-only remediation controls.

## What SDETKit gives teams

- **Deterministic decisions:** every release-confidence run ends in an auditable SHIP / NO-SHIP signal.
- **Evidence-first artifacts:** JSON and Markdown outputs can be reviewed by humans, bots, and CI.
- **Diagnostic investigation:** `sdetkit investigate` explains failures and recommends proof commands without mutating the repository.
- **Guarded automation path:** remediation and PR automation are explicit opt-in lanes, not the default behavior.
- **One workflow everywhere:** use the same core commands locally, in CI, and during operator handoff.

## Core operator lanes

| Lane | Command | Start here when... |
| --- | --- | --- |
| Release gate | `python -m sdetkit gate fast` -> `python -m sdetkit gate release` -> `python -m sdetkit doctor` | You need a ship/no-ship decision. |
| Review | `python -m sdetkit review . --no-workspace --format operator-json` | You need operator-facing findings. |
| Investigation | `python -m sdetkit investigate failure --log build/quality.log --format markdown` | A CI log or PR check needs triage before remediation. |
| CI-ready | `./ci.sh quick --artifact-dir .sdetkit/out` and `make merge-ready` | You want a local CI-equivalent smoke path. |
| First proof | `make first-proof` | You are validating this repository's full first-proof bundle. |

For a guided command router, run:

```bash
make upgrade-next
```

## Product proof

<!-- product-proof-start -->
SDETKit is backed by committed live-adoption proof.

- **Evidence:** `docs/artifacts/live-adoption/product-proof-post-1072/`
- **Decision:** `SHIP with known STRICT_FINDINGS`
- **Blocking failures:** `0`
- **Known strict finding:** `legacy-noargs` compatibility behavior only
- **Proof page:** [`docs/live-adoption-product-proof.md`](docs/live-adoption-product-proof.md)
<!-- product-proof-end -->

For this repository, `make first-proof` emits `FIRST_PROOF_DECISION=SHIP|NO-SHIP` and writes the consolidated bundle under `build/first-proof/`. Use [`docs/upgrade-next-commands.md`](docs/upgrade-next-commands.md), [`docs/first-proof-troubleshooting.md`](docs/first-proof-troubleshooting.md), and [`docs/first-proof-learning-db.md`](docs/first-proof-learning-db.md) for the full first-proof/ops command set.


## Repository layout

| Area | Purpose |
| --- | --- |
| `src/` | SDETKit Python package and CLI implementation. |
| `tests/` | Unit, workflow, docs, and contract tests. |
| `docs/` | Operator guides, artifact references, quality gates, and developer docs. |
| `docs/artifacts/` | Committed generated/sample artifacts and historical proof packs. |
| `.github/workflows/` | CI, quality, maintenance, and artifact upload automation. |

## Documentation map

- Start in 5 minutes: [docs/start-here-5-minutes.md](docs/start-here-5-minutes.md)
- Docs index: [docs/index.md](docs/index.md)
- Operator essentials: [docs/operator-essentials.md](docs/operator-essentials.md)
- Investigation operator guide: [docs/investigation-operator-guide.md](docs/investigation-operator-guide.md)
- Adaptive diagnosis: [docs/adaptive-diagnosis.md](docs/adaptive-diagnosis.md)
- Artifact reference and generated sample map: [docs/artifact-reference.md](docs/artifact-reference.md)
- CI artifact walkthrough: [docs/ci-artifact-walkthrough.md](docs/ci-artifact-walkthrough.md)
- Recommended CI flow: [docs/recommended-ci-flow.md](docs/recommended-ci-flow.md)
- CLI reference: [docs/cli.md](docs/cli.md)
- Portfolio reporting recipe: [docs/portfolio-reporting-recipe.md](docs/portfolio-reporting-recipe.md)
- Portfolio readiness: [docs/portfolio-readiness.md](docs/portfolio-readiness.md)
- Operations handbook: [docs/operations-handbook.md](docs/operations-handbook.md)
- Remediation cookbook: [docs/remediation-cookbook.md](docs/remediation-cookbook.md)

Historical and transition-era references are intentionally secondary. Open the docs index after the canonical first path is working.

## Advanced lanes live in docs

To keep this README readable, advanced command matrices live in focused guides:

- First-proof and operator command router: [docs/upgrade-next-commands.md](docs/upgrade-next-commands.md)
- Multi-repo and portfolio posture: [docs/portfolio-readiness.md](docs/portfolio-readiness.md) and [docs/portfolio-reporting-recipe.md](docs/portfolio-reporting-recipe.md)
- Maintenance and recurring operations: [docs/operations-handbook.md](docs/operations-handbook.md)
- Rollback/remediation examples: [docs/integrations/rollback-remediation-examples.md](docs/integrations/rollback-remediation-examples.md)
- Failure remediation workflow example: [examples/kits/intelligence/failure-fix-playbook.md](examples/kits/intelligence/failure-fix-playbook.md)

## Project policies

- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Security: [SECURITY.md](SECURITY.md)
- Security docs: [docs/security.md](docs/security.md)
- Policy baselines: [docs/policy-and-baselines.md](docs/policy-and-baselines.md)
- Quality playbook: [QUALITY_PLAYBOOK.md](QUALITY_PLAYBOOK.md)
- Release notes: [CHANGELOG.md](CHANGELOG.md)
