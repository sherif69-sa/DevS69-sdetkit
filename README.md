# SDETKit

![CI](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/ci.yml/badge.svg?branch=main)
![Quality](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/quality.yml/badge.svg?branch=main)
![Security](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/security.yml/badge.svg?branch=main)
![Repo Audit](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/repo-audit.yml/badge.svg?branch=main)
![Pages](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/pages.yml/badge.svg?branch=main)

SDETKit is a production-oriented SDET + DevOps toolkit for auditing repositories, running deterministic API checks, enforcing policy gates, and generating release/readiness evidence. It is designed for team adoption: stable outputs, explicit exit codes, CI-friendly commands, and safety-minded defaults.

## Install

Runtime install (minimal dependencies):
- `python -m pip install .`

Developer install (all tooling, pinned toolchain):
- `bash scripts/bootstrap.sh`
- `source .venv/bin/activate`

Optional extras:
- `python -m pip install .[dev]` (includes `pre-commit`)
- `python -m pip install .[test]` (includes `hypothesis` and test runners)

## Quickstart

- Show commands:
  - `python -m sdetkit --help`
  - `python -m sdetkit playbooks`

- Run repository diagnostics:
  - `python -m sdetkit doctor --help`

- Run an API request with deterministic handling:
  - `python -m sdetkit apiget --help`
  - `python -m sdetkit cassette-get --help`

- Run the fast CI-equivalent gate:
  - `bash ci.sh quick --skip-docs`
- Run the full local quality gate:
  - `bash quality.sh all`

## DevOps Quickstart

### Local (WSL2/Linux)
```bash
python -m pip install .
python -m sdetkit gate fast
python -m sdetkit baseline check --format json
python -m sdetkit gate release
```

### GitHub Actions
Use the existing workflow entrypoint command in your job:
```yaml
- name: Install
  run: python -m pip install .[dev,test]
- name: CI gate
  run: bash ci.sh quick --skip-docs
```

### Jenkins
See ready-to-copy references under `examples/ci/jenkins/` (for example `examples/ci/jenkins/jenkins-advanced-reference.Jenkinsfile`).

### Docker
```bash
docker build -t sdetkit .
docker run --rm -v "$PWD:/work" -w /work sdetkit python -m sdetkit gate fast
```

## Tooling overview

Core tools:
- `doctor`       Repo diagnostics and actionable remediation guidance
- `repo`         Repository audit and exportable reports
- `apiget`       API request CLI (supports cassette record/replay)
- `cassette-get` Convenience wrapper for cassette-driven GET flows
- `patch`        Patch and change validation utilities
- `security`     Security and policy gate workflows
- `ops`          Operational workflows and automation helpers
- `report`       Deterministic report generation
- `maintenance`  Maintenance checks and project health commands
- `notify`       Notifications and pluggable notification sinks
- `kv`           Small deterministic KV utilities for scripting
- `dev`          Developer helpers (local DX)

Docs and governance:
- `docs-qa` / `docs-nav`    Docs QA and navigation validation
- `policy` / `evidence`     Governance and evidence helpers
- `roadmap`                 Roadmap/manifest tooling for docs and planning

Playbooks:
- `playbooks` lists legacy playbook flows that are intentionally hidden from the main `--help` output to keep the CLI surface professional. These commands still run directly and are available for teams that want them.

## Determinism and safety

SDETKit aims to be safe by default:
- Deterministic outputs (stable ordering and formatting where applicable)
- CI-friendly exit codes and error messages
- No hidden network calls beyond explicitly invoked commands

## CI usage

Recommended CI entrypoint (single reproducible command):

Opt-in network tests:
- `bash ci.sh quick --skip-docs --run-network`
- `bash ci.sh quick --skip-docs`

This wraps `python -m sdetkit gate fast` (fast profile uses a small pytest subset) while keeping docs builds opt-in.

### Security gate budgets (new)

Use the new `security enforce` command to lock alert budgets in CI and prevent drift over time:
- `python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0`
- `python -m sdetkit security enforce --format json --max-rule SEC_OS_SYSTEM=0 --max-rule SEC_YAML_UNSAFE_LOAD=0`

Tip: pair `security scan --format sarif` (for code scanning upload) with `security enforce` (for deterministic policy budgets).

## Documentation

- Build docs locally:
  - `mkdocs build -s`
- Determinism checklist:
  - `docs/determinism-checklist.md`

## Contributing

- Bootstrap the pinned dev toolchain:
  - `bash scripts/bootstrap.sh`
  - `source .venv/bin/activate`
- Run the local quality gate before opening a PR:
  - `bash quality.sh all`

## Closeout lanes (Days 72-76)

```bash
python -m sdetkit case-study-prep4-closeout --format json --strict
python -m sdetkit case-study-launch-closeout --format json --strict
python -m sdetkit distribution-scaling-closeout --format json --strict
python -m sdetkit trust-assets-refresh-closeout --format json --strict
python -m sdetkit contributor-recognition-closeout --format json --strict
```
