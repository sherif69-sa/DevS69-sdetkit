<div align="center">
  <img src="docs/assets/logo-mark.svg" alt="DevS69 mark" width="68" />
  <h1>DevS69 SDETKit</h1>
  <p><strong>From noisy CI evidence to deterministic ship / no-ship decisions.</strong></p>
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
python -m pip install sdetkit==1.2.0

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

## Why SDETKit?

Most quality tools stop at a failed check. SDETKit connects the evidence into an operator decision:

- **Decide:** produce deterministic `SHIP` / `NO-SHIP` evidence.
- **Diagnose:** extract the first meaningful failure instead of repeating the loudest wrapper error.
- **Prove:** recommend exact verification commands and preserve machine-readable artifacts.
- **Protect:** keep investigation and remediation review-first unless an explicit guarded policy allows more.

## From failure to next action

```text
input: FAILED tests/test_release_contract.py::test_wheel_smoke
classification: test
affected_file: tests/test_release_contract.py
next_command: python -m pytest -q tests/test_release_contract.py -o addopts=
authority: review-first; no repository mutation or merge authorization
```

Start with [`docs/first-failure-triage.md`](docs/first-failure-triage.md) and [`docs/investigation-operator-guide.md`](docs/investigation-operator-guide.md).

## Public launch proof

See the [committed public launch proof](docs/public-launch-proof.md) for a realistic saved pytest failure reduced to its first failing node, affected file, focused proof command, and review-first decision. The same proof includes a fixture-based Python, JavaScript/TypeScript, and Go adoption profile generated without installing target dependencies, executing target code, mutating the target, or authorizing a merge.

The proof is tied to an immutable source commit and is included in the independently verified `sdetkit==1.2.0` public release.

## Decision contract

| Signal | Decision |
| --- | --- |
| `gate-fast.json.ok == true` and `release-preflight.json.ok == true` | ✅ SHIP |
| Any `ok: false` | ❌ NO-SHIP |
| `failed_steps` present in either artifact | ❌ NO-SHIP |

Secondary lanes cover review, investigation, quality, maintenance, and CI automation once the primary gate decision is stable. Investigation/reporting/planning lanes are diagnostic-only by default; repository mutation requires explicit guarded policy and PR-only remediation controls.

## What SDETKit gives teams

- **Deterministic decisions:** every release-confidence run ends in an auditable SHIP / NO-SHIP signal.
- **Evidence-first artifacts:** JSON and Markdown outputs can be reviewed by humans, bots, and CI.
- **Diagnostic investigation:** `sdetkit investigate` explains failures and recommends proof commands without mutating the repository.
- **Guarded automation path:** remediation and PR automation are explicit opt-in lanes, not the default behavior.
- **One workflow everywhere:** use the same core commands locally, in CI, and during operator handoff.

| Lane | Command | Start here when... |
| --- | --- | --- |
| Release gate | `python -m sdetkit gate fast` -> `python -m sdetkit gate release` -> `python -m sdetkit doctor` | You need a ship/no-ship decision. |
| Readiness evidence | `python -m sdetkit repo audit . --format json --fail-on none` → `python -m sdetkit security scan --fail-on none --format sarif --output build/security.sarif --sbom-output build/sbom.cdx.json` → `python -m sdetkit evidence pack --output .sdetkit/out/evidence.zip` | You need local repository, security, and bundled evidence. See [Repo Audit](docs/repo-audit.md), [Security Gate](docs/security-gate.md), and [Artifact reference](docs/artifact-reference.md). |
| Review | `python -m sdetkit review . --no-workspace --format operator-json` | You need operator-facing findings. |
| Investigation | `python -m sdetkit investigate failure --log build/quality.log --format markdown` | A CI log or PR check needs triage before remediation. |
| CI-ready | `./ci.sh quick --artifact-dir .sdetkit/out` and `make merge-ready` | You want a local CI-equivalent smoke path. |

## Product proof

<!-- product-proof-start -->
SDETKit is backed by committed live-adoption proof.

- **Evidence:** `docs/artifacts/live-adoption/product-proof-post-1072/`
- **Decision:** `SHIP with known STRICT_FINDINGS`
- **Blocking failures:** `0`
- **Known strict finding:** `legacy-noargs` compatibility behavior only
- **Proof page:** [`docs/live-adoption-product-proof.md`](docs/live-adoption-product-proof.md)
<!-- product-proof-end -->

For this repository, `make first-proof` emits `FIRST_PROOF_DECISION=SHIP|NO-SHIP` and writes the consolidated bundle under `build/first-proof/`.

## Release channel

The install command above uses the latest published package, `sdetkit==1.2.0`. That release contains the full-product capabilities qualified from source commit `5165a82f8cd2ab3ce6be29737a2afdad58ea85a5`; its PyPI distributions and clean public installation are recorded in the [public release verification log](docs/release-verification.md). Changes merged after that immutable tag are unreleased until a later qualified publication.

## Documentation map

- Start in 5 minutes: [docs/start-here-5-minutes.md](docs/start-here-5-minutes.md)
- Operator essentials: [docs/operator-essentials.md](docs/operator-essentials.md)
- Investigation operator guide: [docs/investigation-operator-guide.md](docs/investigation-operator-guide.md)
- Adaptive diagnosis: [docs/adaptive-diagnosis.md](docs/adaptive-diagnosis.md)
- Public launch proof: [docs/public-launch-proof.md](docs/public-launch-proof.md)
- Artifact reference: [docs/artifact-reference.md](docs/artifact-reference.md)
- Recommended CI flow: [docs/recommended-ci-flow.md](docs/recommended-ci-flow.md)
- CLI reference: [docs/cli.md](docs/cli.md)
- Contributor guide: [CONTRIBUTING.md](CONTRIBUTING.md)

## Advanced lanes live in docs

Historical and transition-era references (secondary) remain outside the first-time path.

- External repository adoption: [docs/adoption.md](docs/adoption.md)
- Portfolio readiness and reporting: [docs/portfolio-readiness.md](docs/portfolio-readiness.md)
- Operations handbook: [docs/operations-handbook.md](docs/operations-handbook.md)
- Remediation cookbook: [docs/remediation-cookbook.md](docs/remediation-cookbook.md)
- Release process: [docs/project/release-process.md](docs/project/release-process.md)

## Top-tier reporting sample pipeline

Run `make top-tier-reporting`; see [docs/portfolio-reporting-recipe.md](docs/portfolio-reporting-recipe.md) and [docs/kpi-schema.md](docs/kpi-schema.md).

## Upgrade next (intent router)

Run `make upgrade-next`; see [docs/upgrade-next-commands.md](docs/upgrade-next-commands.md).

## Real workflow operations

See [docs/real-workflow-operations.md](docs/real-workflow-operations.md). Common aliases: `make ops-daily`, `make ops-daily-fast`, `make ops-weekly`, `make ops-premerge`, `make ops-premerge-fast`, `make ops-premerge-next`, `make ops-premerge-next-fast`, `make ops-followup`, `make ops-now`, `make ops-now-lite`, `make ops-next`.

## Repository layout

| Area | Purpose |
| --- | --- |
| `src/` | SDETKit Python package and CLI implementation. |
| `tests/` | Unit, workflow, docs, and contract tests. |
| `docs/` | Operator guides, artifact references, quality gates, and developer docs, including `docs/artifacts/`. |
| `.github/workflows/` | CI, quality, maintenance, and artifact upload automation. |

## Project policies

- Docs map: [docs/docs-map.md](docs/docs-map.md)
- Security: [SECURITY.md](SECURITY.md)
- Quality playbook: [docs/project/quality-playbook.md](docs/project/quality-playbook.md)
- Release notes: [CHANGELOG.md](CHANGELOG.md)
