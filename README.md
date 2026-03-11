# DevS69 SDETKit

![CI](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/ci.yml/badge.svg?branch=main)
![Quality](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/quality.yml/badge.svg?branch=main)
![Security](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/security.yml/badge.svg?branch=main)
![Repo Audit](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/repo-audit.yml/badge.svg?branch=main)
![Pages](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/pages.yml/badge.svg?branch=main)

SDETKit is a layered **release-confidence and engineering-operations toolkit**. It helps teams move from scattered checks to deterministic workflows, evidence, and repeatable operator experience—so "ready to ship" is a verifiable decision, not a subjective one.

## Why this exists

Most repositories accumulate separate scripts and tools, but the release decision still depends on manual interpretation. SDETKit provides a consistent command path from quick confidence to strict release gating, with machine-readable evidence and CI-safe outcomes.

## Start here

Choose the path that matches where you are now:

### 0) Decide if SDETKit is a fit

- Decision guide: `docs/decision-guide.md`

### 1) Evaluate a repository quickly

```bash
bash scripts/ready_to_use.sh quick
```

- Fast confidence check with deterministic pass/fail output.
- Good first run before deeper enforcement.
- Guide: `docs/ready-to-use.md`

### 2) Run stricter release-confidence checks

```bash
bash scripts/ready_to_use.sh release
```

- Runs a stricter go/no-go lane (quality + security + release gate flow).
- Use before release decisions.
- Overview: `docs/release-confidence.md`

### 3) Understand the broader system and command surface

- Representative adopter walkthrough: `docs/example-adoption-flow.md`
- Full command map: `docs/command-taxonomy.md`
- CLI command reference: `docs/cli.md`

## Who this is for

- **SDET / QA teams** that need reproducible quality and release gates.
- **DevOps / platform teams** that want policy-aware checks in CI.
- **Maintainers and release owners** who need evidence-backed release decisions.

## Why not just separate tools?

- Separate tools can run checks; SDETKit standardizes the operator workflow, output shape, and decision path so teams get repeatable release outcomes.
- SDETKit keeps proof artifacts and governance-oriented outputs close to execution, instead of leaving integration and interpretation fully ad hoc.

Comparison and proof details: `docs/why-not-just-tools.md`

## How to navigate SDETKit

- Decision guide (fit + path + stop point): `docs/decision-guide.md`
- Adoption walkthrough: `docs/example-adoption-flow.md`
- Real artifact output showcase: `docs/evidence-showcase.md`
- Command taxonomy: `docs/command-taxonomy.md`
- Release-confidence model and lanes: `docs/release-confidence.md`
- CLI docs: `docs/cli.md`
- External repository adoption: `docs/adoption.md`
- Troubleshooting first failures: `docs/adoption-troubleshooting.md`
- Scenario-based proof examples: `docs/examples.md`
- Stability levels (current policy): `docs/stability-levels.md`
- Product boundary audit and taxonomy plan: `docs/productization-map.md`

Docs portal: <https://sherif69-sa.github.io/DevS69-sdetkit/>

## Stability levels (current policy)

SDETKit uses four user-facing stability levels: **Stable/Core**, **Integrations**, **Playbooks**, and **Experimental**.

- Start production rollout with **Stable/Core** release-confidence flows.
- Add **Integrations** after validating platform-specific behavior.
- Use **Playbooks** for guided adoption and operational lanes.
- Treat **Experimental** lanes (including day/closeout families) as opt-in transition-era or advanced flows.

Policy doc: `docs/stability-levels.md`

## Core commands

```bash
# Fast confidence lane
bash scripts/ready_to_use.sh quick

# Strict release-confidence lane
bash scripts/ready_to_use.sh release

# Direct CLI gates
python -m sdetkit gate fast
python -m sdetkit gate release

# Security budget enforcement
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0
```

Explore broader command domains (`doctor`, `repo`, `security`, `evidence`, `report`, `ops`):

```bash
python -m sdetkit --help
python -m sdetkit playbooks
```

## Installation

### Runtime install

```bash
python -m pip install .
```

### Developer install (recommended)

```bash
bash scripts/bootstrap.sh
source .venv/bin/activate
```

### Optional extras

```bash
python -m pip install .[dev]
python -m pip install .[test]
python -m pip install .[packaging]
```

## CI/CD integration

For teams adopting SDETKit in another repository, start with:

- `docs/adoption.md` for copy-paste local and GitHub Actions workflows.
- `docs/recommended-ci-flow.md` for the recommended baseline CI shape (PR fast feedback, stricter `main`, release-oriented checks).
- First gate: `python -m sdetkit gate fast`
- Stricter rollout: security budgets + `python -m sdetkit gate release`

For CI failure triage in this repository's GitHub Actions runs, inspect uploaded artifacts:

- `ci-gate-diagnostics` (`build/gate-fast.json`, `build/security-enforce.json`)
- `release-diagnostics` (`build/release-preflight.json`)

For an immediate "downloaded artifact -> next fix step" path, use the artifact-to-action map in `docs/adoption-troubleshooting.md`.

### Jenkins

See `examples/ci/jenkins/`.

### Docker

```bash
docker build -t sdetkit .
docker run --rm -v "$PWD:/work" -w /work sdetkit python -m sdetkit gate fast
```

## Contributor entry points

- Contributing guide: `CONTRIBUTING.md`
- First-time contributor quickstart: `docs/first-contribution-quickstart.md`
- Starter work inventory: `docs/starter-work-inventory.md`
- Maintainer starter-issue hygiene: `docs/maintainer-starter-issue-hygiene.md`
- First contribution command: `python -m sdetkit first-contribution --format text --strict`

## Release posture note

This repository is prepared for artifact build and release validation. Public PyPI publication depends on `PYPI_API_TOKEN` configuration and successful workflow execution; this README does not claim generally available PyPI distribution by default.

For first-public-release and post-release external verification steps, follow `RELEASE.md` and `docs/releasing.md`. After real releases are verified externally, see `docs/release-verification.md` for published evidence records.

## License

Distributed under the Apache-2.0 license. See `LICENSE` and `ENTERPRISE_OFFERINGS.md`.
