# DevS69 SDETKit

![CI](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/ci.yml/badge.svg?branch=main)
![Quality](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/quality.yml/badge.svg?branch=main)
![Security](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/security.yml/badge.svg?branch=main)
![Repo Audit](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/repo-audit.yml/badge.svg?branch=main)
![Pages](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/pages.yml/badge.svg?branch=main)

SDETKit helps teams **prove release confidence** with deterministic checks and audit-friendly evidence.

## What this is (10-second version)

SDETKit is a release-confidence toolkit.

It gives teams one repeatable answer to: **"Is this repository ready to ship?"**

If you want one command path from quick confidence to a strict release gate (with evidence you can review later), start here.

## The one thing this repo is best at

SDETKit is centered on one flagship workflow: **release confidence gating**.

Run one command sequence to answer: _"Is this repository ready to ship?"_

```bash
bash scripts/ready_to_use.sh release
```

This runs environment bootstrap + CI quick lane + coverage + security enforcement + release gate in a repeatable flow.

---

## Start here (first 5 minutes)

### 1) Run the fastest path (quick confidence)

```bash
bash scripts/ready_to_use.sh quick
```

### 2) What to expect

- Bootstraps a local virtual environment.
- Verifies the CLI is healthy.
- Runs `ci.sh quick --skip-docs`.
- Prints a clear status and next step.

### 3) Value proof

If this command finishes, you have a working local gate path that mirrors CI expectations and gives deterministic pass/fail output.

### 4) Move to strict release gate

```bash
bash scripts/ready_to_use.sh release
```

Use release mode when you want a stricter go/no-go decision before a release.

Ready-to-use guide: `docs/ready-to-use.md`

Release-confidence overview: `docs/release-confidence.md`

## Core path (local and CI)

Use this progression:

1. **Quick confidence:** `bash scripts/ready_to_use.sh quick`
2. **Strict release gate:** `bash scripts/ready_to_use.sh release`
3. **Adopt in external repo:** `docs/adoption.md`

This keeps the journey focused on release confidence first, then rollout.

## Adopt in your own repository (external integration)

Focused remediation playbooks: `docs/remediation-cookbook.md`

If you want to use SDETKit in a different repository, use the adopter-focused guide:

- `docs/adoption.md`
- `docs/adoption-troubleshooting.md` for first-failure triage (what failed, what it means, what to do next).
- Includes copy-paste local + CI integration patterns.
- Shows a progressive path from lightweight `gate fast` to stricter release gating.

## Proof by scenario

Want concrete examples before adopting?

- See **3 realistic release-confidence scenarios** in `docs/examples.md`.
- See a **representative first-run-to-release adoption walkthrough** in `docs/example-adoption-flow.md`.
- Each scenario includes: situation, command, representative output, and maintainer next action.

```bash
# quick confidence lane
bash scripts/ready_to_use.sh quick

# strict release lane
bash scripts/ready_to_use.sh release
```

---

## Who this is for

- **SDET / QA** teams that need reproducible quality gates.
- **DevOps / platform** teams that want policy-aware release checks in CI.
- **Maintainers** who need machine-readable evidence for release decisions.

## What you get

- Deterministic command behavior and CI-safe exit codes.
- A structured release-confidence workflow instead of ad-hoc scripts.
- Evidence-oriented outputs for review, governance, and handoffs.

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

## Flagship workflow (manual form)

If you want the release-confidence workflow step-by-step:

```bash
bash ci.sh quick --skip-docs
bash quality.sh cov
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0
python -m sdetkit gate release
```

## Explore commands (core first)

### Core release-confidence commands

```bash
bash scripts/ready_to_use.sh quick
bash scripts/ready_to_use.sh release
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0
```

### Broader toolkit commands

```bash
python -m sdetkit --help
python -m sdetkit playbooks
```

Command domains include `doctor`, `repo`, `security`, `evidence`, `report`, and `ops`.

## Docs and contributor entry points

- Docs portal: <https://sherif69-sa.github.io/DevS69-sdetkit/>
- Quickstart doc: `docs/ready-to-use.md`
- System-value comparison: `docs/why-not-just-tools.md`
- Contributing guide: `CONTRIBUTING.md`
- First-time contributor quickstart: `docs/first-contribution-quickstart.md`
- Starter work inventory: `docs/starter-work-inventory.md`
- Maintainer starter-issue hygiene: `docs/maintainer-starter-issue-hygiene.md`
- First contribution command: `python -m sdetkit first-contribution --format text --strict`

## New contributors: fastest safe first PR

If you already ran `bash scripts/ready_to_use.sh quick`, use this path to make a first contribution quickly.

1. Read `docs/first-contribution-quickstart.md` and pick a small contribution type.
2. Check `docs/starter-work-inventory.md` for concrete starter categories tied to this repo.
3. Set up your environment with `bash scripts/bootstrap.sh`.
4. Make one focused change (docs/example, test, lint fix, or CLI/docs alignment).
5. Run `python -m pre_commit run -a` and `bash quality.sh cov` before opening a PR.

If you cannot find a starter issue, use `docs/starter-work-inventory.md` and open a scoped proposal with the Feature request template, noting it is a first contribution.

## CI/CD integration

For teams adopting SDETKit in another repository, start with:

- `docs/adoption.md` for copy-paste local and GitHub Actions workflows.
- First gate: `python -m sdetkit gate fast`
- Stricter rollout: security budgets + `python -m sdetkit gate release`

For CI failure triage in this repository's GitHub Actions runs, inspect uploaded artifacts:

- `ci-gate-diagnostics` (`build/gate-fast.json`, `build/security-enforce.json`)
- `release-diagnostics` (`build/release-preflight.json`)

This keeps `failed_steps` and policy threshold outcomes easy to inspect without depending only on log scrolling.

For an immediate "downloaded artifact -> next fix step" path, start at the **Artifact-to-action map** in `docs/adoption-troubleshooting.md`.

### Jenkins

See `examples/ci/jenkins/`.

### Docker

```bash
docker build -t sdetkit .
docker run --rm -v "$PWD:/work" -w /work sdetkit python -m sdetkit gate fast
```

## Release posture note

This repository is prepared for artifact build and release validation. Public PyPI publication depends on `PYPI_API_TOKEN` configuration and successful workflow execution; this README does not claim generally available PyPI distribution by default.

For first-public-release and post-release external verification steps, follow `RELEASE.md` and `docs/releasing.md`.
After real releases are verified externally, see `docs/release-verification.md` for published evidence records.

## License

Distributed under the Apache-2.0 license. See `LICENSE` and `ENTERPRISE_OFFERINGS.md`.
