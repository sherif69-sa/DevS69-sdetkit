# SDETKit

SDETKit is a production-oriented SDET + DevOps toolkit for auditing repositories, running deterministic API checks, enforcing policy gates, and generating release/readiness evidence. It is designed for team adoption: stable outputs, explicit exit codes, CI-friendly commands, and safety-minded defaults.

## Install

Runtime install (minimal dependencies):
- `python -m pip install sdetkit`

Developer install (all tooling):
- `python -m pip install -e '.[dev,test,docs]'`

## Quickstart

- Show commands:
  - `python -m sdetkit --help`
  - `python -m sdetkit playbooks`

- Run repository diagnostics:
  - `python -m sdetkit doctor --help`

- Run an API request with deterministic handling:
  - `python -m sdetkit apiget --help`
  - `python -m sdetkit cassette-get --help`

- Run the full local quality gate (same as CI):
  - `bash quality.sh all`

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

Recommended CI entrypoint:
- `bash quality.sh all`

This runs formatting/linting, typing, and tests using the repo's pinned tooling.

## Documentation

- Build docs locally:
  - `mkdocs build -s`

## Contributing

- Use a virtualenv and install extras:
  - `python -m pip install -e '.[dev,test,docs]'`
- Run the local quality gate before opening a PR:
  - `bash quality.sh all`
