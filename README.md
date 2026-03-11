# DevS69 SDETKit

![CI](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/ci.yml/badge.svg?branch=main)
![Quality](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/quality.yml/badge.svg?branch=main)
![Security](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/security.yml/badge.svg?branch=main)
![Repo Audit](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/repo-audit.yml/badge.svg?branch=main)
![Pages](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/pages.yml/badge.svg?branch=main)

SDETKit is a layered **release-confidence and engineering-operations toolkit**. It helps teams move from scattered checks to deterministic workflows, evidence, and repeatable operator experience—so "ready to ship" is a verifiable decision, not a subjective one.

## Why this exists

Most repositories accumulate separate scripts and tools, but the release decision still depends on manual interpretation. SDETKit provides a consistent command path from quick confidence to strict release gating, with machine-readable evidence and CI-safe outcomes.

## Start here: core release-confidence path

If you're new to SDETKit, start with the **Stable/Core** shipping-readiness path first:

- Install first: see [Installation](#installation)
- Verify install in under 60 seconds: see [Verify your install](#verify-your-install)
- Then run the core path below (`quick` → `release`)

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

### 3) Expand deliberately after core gates are working

- Command-family contract and starting defaults: `docs/command-surface.md`
- Capability map and command taxonomy: `docs/command-taxonomy.md`
- Full CLI command reference: `docs/cli.md`
- Representative adopter walkthrough: `docs/example-adoption-flow.md`
- Scenario-based adoption examples: `docs/adoption-examples.md`

## Recommended expansion order

Keep first-time rollout focused to avoid identity drift:

1. **Stable/Core:** run `quick` then `release` and confirm deterministic go/no-go output.
2. **Integrations:** wire core checks into CI/platform flows after local confidence is established.
3. **Playbooks:** add guided rollout/adoption lanes for team operating rhythms.
4. **Experimental (transition-era):** use day/closeout material only when intentionally needed.

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
- Adoption scenarios: `docs/adoption-examples.md`
- Real artifact output showcase: `docs/evidence-showcase.md`
- Command taxonomy: `docs/command-taxonomy.md`
- Release-confidence model and lanes: `docs/release-confidence.md`
- CLI docs: `docs/cli.md`
- External repository adoption: `docs/adoption.md`
- Troubleshooting first failures: `docs/adoption-troubleshooting.md`
- Compact first-failure triage (core path): `docs/first-failure-triage.md`
- Scenario-based proof examples: `docs/examples.md`
- Stability levels (current policy): `docs/stability-levels.md`
- Versioning and support posture (current policy): `docs/versioning-and-support.md`
- Product boundary audit and taxonomy plan: `docs/productization-map.md`

### Secondary and transition-era material

Historical day/closeout pages remain available for compatibility, audit trails, and specialized programs. They are intentionally **not** the primary onboarding path for first-time adopters.

Docs portal: <https://sherif69-sa.github.io/DevS69-sdetkit/>

## Stability levels (current policy)

SDETKit uses four user-facing stability levels: **Stable/Core**, **Integrations**, **Playbooks**, and **Experimental**.

- Start production rollout with **Stable/Core** release-confidence flows.
- Add **Integrations** after validating platform-specific behavior.
- Use **Playbooks** for guided adoption and operational lanes.
- Treat **Experimental** lanes (including day/closeout families) as opt-in transition-era or advanced flows.

Policy docs: `docs/stability-levels.md`, `docs/versioning-and-support.md`

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

SDETKit currently supports two explicit install paths:

- **From source (this repository)** for contributors/maintainers.
- **From GitHub URL** for external adopters until PyPI publication is verified.

### From source (local clone)

```bash
python -m pip install .
```

### From GitHub (external repository adoption)

```bash
python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
```

### Developer install (recommended in this repo)

```bash
bash scripts/bootstrap.sh
source .venv/bin/activate
```

### Optional extras (choose only what you need)

| Extra | Installs | Use when |
|---|---|---|
| `dev` | linting, typing, packaging helper tooling | You are contributing to this repository. |
| `test` | pytest and test helpers | You need to run/extend tests. |
| `docs` | mkdocs + theme | You need to build docs locally. |
| `packaging` | build/twine/wheel validation tooling | You are validating release artifacts. |
| `telegram` | telegram notifier dependency | You need Telegram notifier integration. |
| `whatsapp` | Twilio notifier dependency | You need WhatsApp notifier integration. |

```bash
python -m pip install .[dev]
python -m pip install .[test]
python -m pip install .[docs]
python -m pip install .[packaging]
python -m pip install .[telegram]
python -m pip install .[whatsapp]
```

You can combine extras as needed, for example:

```bash
python -m pip install .[dev,test,docs]
```

## Verify your install

Run this short check immediately after installation:

```bash
python -m sdetkit --help
python -m sdetkit gate --help
```

Expected result: both commands print usage/help text and exit successfully.

Then run the first real release-confidence signal:

```bash
bash scripts/ready_to_use.sh quick
```

If you installed SDETKit in another repository (without this repo's scripts), use:

```bash
python -m sdetkit gate fast
```

## Recommended first 10 minutes

1. Install SDETKit (local clone or GitHub URL).
2. Verify CLI availability with `python -m sdetkit --help`.
3. Run quick confidence: `bash scripts/ready_to_use.sh quick` (or `python -m sdetkit gate fast` in external repos).
4. Run strict release checks: `bash scripts/ready_to_use.sh release`.
5. Review command families in `docs/cli.md` and staged rollout guidance in `docs/adoption.md`.

What works without optional extras:

- Core gate commands (`gate fast`, `gate release`)
- Security budget enforcement (`security enforce`)
- Stable/Core quickstart wrapper (`scripts/ready_to_use.sh` in this repository)

Optional extras are only for specialized workflows (contributing, docs authoring, packaging validation, notifier integrations).

## CI/CD integration

For teams adopting SDETKit in another repository, start with:

- `docs/adoption.md` for copy-paste local and GitHub Actions workflows.
- `docs/adoption-examples.md` for practical rollout shapes by team/repo context.
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
