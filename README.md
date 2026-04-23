<div align="center">
  <img src="docs/assets/logo-mark.svg" alt="DevS69 mark" width="68" />
  <h1>DevS69 SDETKit</h1>
  <p><strong>Deterministic release confidence for ship / no-ship decisions.</strong></p>
</div>

DevS69 SDETKit is a release-confidence CLI that helps teams run repeatable checks, produce machine-readable evidence, and decide whether a change is ready to ship.

## Why teams use SDETKit

- **Deterministic decisions**: every run ends in a clear SHIP / NO-SHIP outcome.
- **Evidence first**: JSON artifacts can be audited by humans, bots, and CI.
- **One workflow everywhere**: use the same commands locally and in pipelines.

## Quick start (recommended)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install sdetkit==1.0.3

python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

Generated artifacts:

```text
build/
├── gate-fast.json
└── release-preflight.json
```

## Ship / no-ship decision contract

| Signal | Decision |
|---|---|
| `gate-fast.json.ok == true` and `release-preflight.json.ok == true` | ✅ SHIP |
| Any `ok: false` | ❌ NO-SHIP |
| `failed_steps` present in either artifact | ❌ NO-SHIP |

## Core operator lanes

### 1) Release gate lane

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

### 2) Review lane

```bash
python -m sdetkit review . --no-workspace --format json
python -m sdetkit review . --no-workspace --format operator-json
```

### 3) Quality lane

```bash
python -m pip install -r requirements-test.txt
PYTHONPATH=src python -m sdetkit.test_bootstrap_contract --strict
PYTHONPATH=src pytest -q
ruff check .
```

### 4) CI-ready lane (minimal)

```bash
./ci.sh quick --artifact-dir .sdetkit/out
make merge-ready
```

## Top-tier reporting sample pipeline

```bash
make top-tier-reporting
```

Related docs:
- [Portfolio reporting recipe](docs/portfolio-reporting-recipe.md)
- [KPI schema](docs/kpi-schema.md)

## Documentation map

- Start in 5 minutes: [docs/start-here-5-minutes.md](docs/start-here-5-minutes.md)
- Recommended CI flow: [docs/recommended-ci-flow.md](docs/recommended-ci-flow.md)
- Artifact walkthrough: [docs/ci-artifact-walkthrough.md](docs/ci-artifact-walkthrough.md)
- CLI reference: [docs/cli.md](docs/cli.md)
- Docs index: [docs/index.md](docs/index.md)

## Project policies

- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Security: [SECURITY.md](SECURITY.md)
- Quality playbook: [QUALITY_PLAYBOOK.md](QUALITY_PLAYBOOK.md)
- Release notes: [CHANGELOG.md](CHANGELOG.md)
