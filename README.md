# DevS69 SDETKit

![CI](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/ci.yml/badge.svg?branch=main)
![Quality](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/quality.yml/badge.svg?branch=main)
![Security](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/security.yml/badge.svg?branch=main)
![Repo Audit](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/repo-audit.yml/badge.svg?branch=main)
![Pages](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/pages.yml/badge.svg?branch=main)
![Docs Link Check](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/docs-link-check.yml/badge.svg?branch=main)

SDETKit gives engineering teams **deterministic release-confidence checks and evidence** so shipping decisions are fast, consistent, and audit-ready.

## Why this exists

Most teams can run tools; fewer teams can make a repeatable release decision. SDETKit defines a core command path that produces deterministic pass/fail outcomes plus evidence-backed outputs you can trust in local runs and CI.

## Proof of value (concrete, fast, honest)

New here? Start with proof pages grounded in real SDETKit commands and artifact shapes:

- **Blank repo to value in 60 seconds**: `docs/blank-repo-to-value-60-seconds.md`
- **Before/after evidence example**: `docs/before-after-evidence-example.md`
- **SDETKit vs ad hoc scripts and separate tools**: `docs/sdetkit-vs-ad-hoc.md`
- **Team rollout scenario**: `docs/team-rollout-scenario.md`

## See it in action

Terminal demo GIF/video: **not yet checked in**.

When available, place the asset at `docs/assets/sdetkit-terminal-demo.gif` and link/embed it here and in the docs home page.

## Install in 10 seconds

**Recommended (external users):**

```bash
python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
python -m sdetkit --help
```

Why this is the canonical path today:

- It works in any repository without cloning this repo first.
- It does not depend on repo-local helper scripts.
- PyPI install is not yet verified/publicly recorded for this project.

Secondary install options are in [docs/install.md](docs/install.md) (`pipx`, `uv tool install`, local source install for contributors).

## Start here (core adoption path)

For first-time adoption, focus on these five hero paths only:

1. **Install** → [Installation](#installation)
2. **Gate fast** → `python -m sdetkit gate fast`
3. **Gate release** → `python -m sdetkit gate release`
4. **Doctor** → `python -m sdetkit doctor`
5. **Evidence / report output** → `python -m sdetkit evidence --help` and `python -m sdetkit report --help`

### 0) Confirm product fit

- Decision guide: `docs/decision-guide.md`

### 1) Install and verify

```bash
python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
python -m sdetkit --help
```

### 2) Run the core gates

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
```

### 3) Validate environment health and output evidence

```bash
python -m sdetkit doctor
python -m sdetkit evidence --help
python -m sdetkit report --help
```

## Core commands (copy/paste)

```bash
# Optional wrapper lane in this repository
bash scripts/ready_to_use.sh quick
bash scripts/ready_to_use.sh release

# Core CLI gates
python -m sdetkit gate fast
python -m sdetkit gate release

# Environment diagnostics
python -m sdetkit doctor

# Evidence and reporting surfaces
python -m sdetkit evidence --help
python -m sdetkit report --help
```

## Discover later (secondary)

After the five hero paths are working, expand deliberately:

- Release-confidence model: `docs/release-confidence.md`
- CI rollout: `docs/recommended-ci-flow.md`, `docs/adoption.md`
- Capability taxonomy and full CLI depth: `docs/command-taxonomy.md`, `docs/cli.md`
- Integrations/playbooks/history: see docs portal navigation

Historical and transition-era material remains available for compatibility and audit trails, but is intentionally secondary to core adoption.

Docs portal: <https://sherif69-sa.github.io/DevS69-sdetkit/>

## Installation

See the canonical install guide: [docs/install.md](docs/install.md).

Quick reference:

- **Recommended for first-time users:**

  ```bash
  python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
  ```

- **Alternatives:** `pipx`, `uv tool install`, or local source install (`python -m pip install .`) for contributors.

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

Then run the first real release-confidence signal in your own repository:

```bash
python -m sdetkit gate fast
```

## Recommended first 10 minutes

1. Install SDETKit (recommended: GitHub URL install).
2. Verify CLI availability with `python -m sdetkit --help`.
3. Run quick confidence: `python -m sdetkit gate fast`.
4. Run strict release checks: `python -m sdetkit gate release`.
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
