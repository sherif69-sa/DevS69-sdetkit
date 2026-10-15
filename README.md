<div align="center">
  <img src="docs/assets/logo-mark.svg" alt="DevS69 mark" width="68" />
  <h1>DevS69 SDETKit</h1>
  <p><strong>From noisy CI evidence to deterministic ship / no-ship decisions.</strong></p>

  <p>
    <a href="https://pypi.org/project/sdetkit/"><img src="https://img.shields.io/pypi/v/sdetkit?label=PyPI" alt="PyPI version" /></a>
    <a href="https://pypi.org/project/sdetkit/"><img src="https://img.shields.io/pypi/pyversions/sdetkit" alt="Supported Python versions" /></a>
    <a href="https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/ci.yml"><img src="https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI status" /></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License: Apache-2.0" /></a>
    <a href="https://sherif69-sa.github.io/DevS69-sdetkit/"><img src="https://img.shields.io/badge/docs-online-informational" alt="Documentation" /></a>
  </p>

  <p>
    <a href="#quick-start">Quick start</a> ·
    <a href="#how-it-works">How it works</a> ·
    <a href="#proven-on-real-projects">Real-project proof</a> ·
    <a href="https://sherif69-sa.github.io/DevS69-sdetkit/">Documentation</a> ·
    <a href="CONTRIBUTING.md">Contributing</a>
  </p>
</div>

DevS69 SDETKit is a release-confidence CLI for deterministic ship/no-ship decisions with machine-readable evidence. It runs your repository's own checks, reduces any failure to the first one that matters, and tells you the exact command to run next.

**Primary outcome:** know if a change is ready to ship.
**Runtime requirement:** Python 3.10+.

Canonical first path: `python -m sdetkit gate fast` -> `python -m sdetkit gate release` -> `python -m sdetkit doctor`.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install sdetkit==1.2.0

python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
```

Each command writes one JSON artifact that people, bots and CI read the same way:

```text
build/
├── gate-fast.json          # lint, format, types and tests: the fast verdict
├── release-preflight.json  # release readiness: doctor, security scan, gate fast
└── doctor.json             # repository and environment health
```

## What a decision looks like

Every run ends in one verdict (`SHIP`, `REVIEW`, `NOT_RUN` or `NO_SHIP`) and a next-action card:

```text
decision: NO-SHIP
classification: test
first_failure: FAILED tests/test_release_contract.py::test_wheel_smoke
affected_file: tests/test_release_contract.py
next_command: python -m pytest -q tests/test_release_contract.py -o addopts=
authority: review-first
```

| Signal | Decision |
| --- | --- |
| `gate-fast.json.ok == true` and `release-preflight.json.ok == true` | ✅ SHIP |
| Any `ok: false` | ❌ NO-SHIP |
| `failed_steps` present in either artifact | ❌ NO-SHIP |
| A check could not run against the repository (for example, the project is not installed) | ⏸ NOT_RUN, with the setup command |

## How it works

| Step | Command | What it does |
| --- | --- | --- |
| Fast gate | `python -m sdetkit gate fast` | Runs the checks your repository configures (ruff, mypy, pytest, and Go, JavaScript, Rust, Java, .NET or C++ test suites) in the project's own environment. |
| Release gate | `python -m sdetkit gate release` | Runs `doctor --release`, an offline security scan and the fast gate, and combines them into one release verdict. |
| Health check | `python -m sdetkit doctor` | Checks the repository and environment: lockfiles, CI, clean tree, tooling. |
| Fix loop | `python -m sdetkit diagnose run --prove` | Diagnoses the latest failing gate, proves the narrowest mechanical fix in a throwaway copy, and writes a decision card for a person to approve. Nothing is applied for you. |

Configuration is optional. `gate fast` follows the policy your repository already declares, and `[tool.sdetkit.gate]` in `pyproject.toml` overrides it; see the [CLI reference](docs/cli.md).

### Fix a failing CI job

```bash
python -m sdetkit diagnose run --log build/ci-logs/lint/ci_log.txt --prove
python -m sdetkit diagnose decide --card build/sdetkit/remediation-loop/decision-card.json --approve --reviewer <you>
```

After a failing local `gate fast`, `python -m sdetkit diagnose run --prove` picks up the failed steps on its own. See the [remediation loop](docs/remediation-loop.md) and [first-failure triage](docs/first-failure-triage.md).

## Proven on real projects

`gate fast` has been run on seven well-known open-source projects at pinned commits. Each ran once on a fresh clone and once after the setup command SDETKit suggests. After setup, pallets/itsdangerous, markupsafe and click, pytest-dev/pluggy and python-poetry/poetry-core read SHIP; python-attrs/attrs and psf/requests read NO_SHIP. The page records every result as it came out, including the ones SDETKit still gets wrong: [external repository proof](docs/external-repo-proof.md).

<!-- product-proof-start -->
SDETKit is also backed by committed live-adoption proof.

- **Evidence:** `docs/artifacts/live-adoption/product-proof-post-1072/`
- **Decision:** `SHIP with known STRICT_FINDINGS`
- **Blocking failures:** `0`
- **Known strict finding:** `legacy-noargs` compatibility behavior only
- **Proof page:** [`docs/live-adoption-product-proof.md`](docs/live-adoption-product-proof.md)
<!-- product-proof-end -->

The [public launch proof](docs/public-launch-proof.md) reduces a saved pytest failure to its first failing node, affected file and focused proof command. For this repository, `make first-proof` emits `FIRST_PROOF_DECISION=SHIP|NO-SHIP` and writes its bundle under `build/first-proof/`.

## Safety boundaries

- **Review-first by default.** SDETKit diagnoses and recommends; it does not apply patches, merge, or dismiss findings. Every authority flag in its output (`automation_allowed`, `patch_application_allowed`, `merge_authorized`, and the others) is `false`.
- **Proof in isolation.** `diagnose run --prove` tests candidate fixes in a throwaway copy, never in your working tree.
- **Your code runs.** `gate fast` runs your repository's own tests and tools, so run it on code you would run `pytest` on. See the [security policy](SECURITY.md).

## Release channel

The install command above uses the latest published package, `sdetkit==1.2.0`. That release contains the full-product capabilities qualified from source commit `5165a82f8cd2ab3ce6be29737a2afdad58ea85a5`; its PyPI distributions and clean public installation are recorded in the [public release verification log](docs/release-verification.md).

The `main` branch is the 2.0.0 release candidate: a smaller CLI, one verdict, the local remediation loop from a failing gate to a reviewed fix, accumulating RepoMemory, first-run reliability fixes, and checks that run in the project's own environment. Those capabilities remain **main-only** until the qualified 2.0.0 release; see the [current product delta](docs/current-product-delta.md) and the 2.0.0 upgrade notes in [CHANGELOG.md](CHANGELOG.md).

## Documentation

| Start | Operate | Reference |
| --- | --- | --- |
| [Start in 5 minutes](docs/start-here-5-minutes.md) | [Operator essentials](docs/operator-essentials.md) | [CLI reference](docs/cli.md) |
| [First-failure triage](docs/first-failure-triage.md) | [Investigation guide](docs/investigation-operator-guide.md) | [Artifact reference](docs/artifact-reference.md) |
| [Recommended CI flow](docs/recommended-ci-flow.md) | [Adaptive diagnosis](docs/adaptive-diagnosis.md) | [Docs map](docs/docs-map.md) |

More lanes (repository audit, security scan, evidence packs, review, investigation) are in the [full documentation](https://sherif69-sa.github.io/DevS69-sdetkit/). `make help` lists the developer targets.

Historical and transition-era references (secondary) remain outside the first-time path: [external repository adoption](docs/adoption.md), [operations handbook](docs/operations-handbook.md), [remediation cookbook](docs/remediation-cookbook.md) and the [release process](docs/project/release-process.md).

## Community

- [Contributing guide](CONTRIBUTING.md): set up, validate and open a pull request.
- [Security policy](SECURITY.md): report a vulnerability privately.
- [Code of conduct](CODE_OF_CONDUCT.md): how we work together.
- [Support](SUPPORT.md): where to ask for help.
- [Changelog](CHANGELOG.md): what changed in each release.

## License

SDETKit is released under the [Apache License 2.0](LICENSE).
