# DevS69 SDETKit

![CI](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/ci.yml/badge.svg?branch=main)
![Quality](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/quality.yml/badge.svg?branch=main)
![Security](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/security.yml/badge.svg?branch=main)
![Repo Audit](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/repo-audit.yml/badge.svg?branch=main)
![Pages](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/pages.yml/badge.svg?branch=main)

SDETKit helps **SDET, QA, and DevOps teams prove release confidence** with deterministic local/CI checks and audit-friendly evidence.

## The one thing this repo is best at

SDETKit is centered on one flagship workflow: **release confidence gating**.

Run one command sequence to answer: _"Is this repository ready to ship?"_

```bash
bash scripts/ready_to_use.sh release
```

This runs environment bootstrap + CI quick lane + coverage + security enforcement + release gate in a repeatable flow.

---

## Start here (first 5 minutes)

### 1) Run the fastest path

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

### 4) Next command

```bash
bash scripts/ready_to_use.sh release
```

Use release mode when you want a stricter go/no-go decision before a release.

Ready-to-use guide: `docs/ready-to-use.md`

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

## Explore core commands

```bash
python -m sdetkit --help
python -m sdetkit playbooks
```

Command domains include `doctor`, `repo`, `security`, `evidence`, `report`, and `ops`.

## Docs and contributor entry points

- Docs portal: <https://sherif69-sa.github.io/DevS69-sdetkit/>
- Quickstart doc: `docs/ready-to-use.md`
- Contributing guide: `CONTRIBUTING.md`
- First contribution command: `python -m sdetkit first-contribution --format text --strict`

## CI/CD integration

### GitHub Actions

```yaml
- name: Install
  run: python -m pip install .[dev,test]
- name: CI gate
  run: bash ci.sh quick --skip-docs
```

### Jenkins

See `examples/ci/jenkins/`.

### Docker

```bash
docker build -t sdetkit .
docker run --rm -v "$PWD:/work" -w /work sdetkit python -m sdetkit gate fast
```

## Release posture note

This repository is prepared for artifact build and release validation. Public PyPI publication depends on `PYPI_API_TOKEN` configuration and successful workflow execution; this README does not claim generally available PyPI distribution by default.

## License

Distributed under the Apache-2.0 license. See `LICENSE` and `ENTERPRISE_OFFERINGS.md`.
