<div align="center">
  <img src="docs/assets/devs69-hero.svg" alt="DevS69 Hero" width="100%" />

  <h1>DevS69 (sdetkit)</h1>
  <p>
    <strong>Production-ready SDET toolkit</strong> with enterprise-grade quality gates,
    security-first workflows, and testable-by-design engineering standards.
  </p>

  <p>
    <a href="https://sherif69-sa.github.io/DevS69-sdetkit/"><strong>🌐 Live Experience Portal</strong></a>
    ·
    <a href="docs/index.md"><strong>📚 Documentation</strong></a>
    ·
    <a href="CONTRIBUTING.md"><strong>🤝 Contribute</strong></a>
  </p>

  <p>
    <a href="https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/ci.yml"><img src="https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
    <a href="https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/quality.yml"><img src="https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/quality.yml/badge.svg?branch=main" alt="Quality"></a>
    <a href="https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/mutation-tests.yml"><img src="https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/mutation-tests.yml/badge.svg?branch=main" alt="Mutation Tests"></a>
    <a href="https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/security.yml"><img src="https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/security.yml/badge.svg?branch=main" alt="Security"></a>
    <a href="https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/pages.yml"><img src="https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/pages.yml/badge.svg?branch=main" alt="Pages"></a>
  </p>

  <p>
    <a href="https://github.com/sherif69-sa/DevS69-sdetkit/releases"><img src="https://img.shields.io/github/v/release/sherif69-sa/DevS69-sdetkit?sort=semver" alt="Latest Release"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-Noncommercial%20%2B%20Commercial%20Required-blue" alt="License"></a>
    <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python">
    <a href="https://github.com/sherif69-sa/DevS69-sdetkit/security/code-scanning"><img src="https://img.shields.io/badge/security-code%20scanning-success" alt="Code Scanning"></a>
    <a href="https://github.com/sherif69-sa/DevS69-sdetkit/security/dependabot"><img src="https://img.shields.io/badge/dependencies-auto%20update-success" alt="Dependabot"></a>
  </p>
</div>

---

## Platform spotlight

> **First-impression boost:** polished onboarding, always-on security scans, strong quality gates, and contributor-ready guidance — aligned with the live portal at **[sherif69-sa.github.io/DevS69-sdetkit](https://sherif69-sa.github.io/DevS69-sdetkit/)**.

## Fast entry paths

| What you need | Start here | Outcome |
|---|---|---|
| Get up and running quickly | [Quick start](#quick-start) | Ready-to-run local environment + first quality pass |
| Understand repository layout | [Repo tour](docs/repo-tour.md) | Role-based orientation and architecture map |
| Use CLI commands effectively | [CLI guide](docs/cli.md) | Practical usage patterns and examples |
| Diagnose repository health | [Doctor docs](docs/doctor.md) | Health checks and recommendations |
| Run safe checks and targeted fixes | [Repo audit](docs/repo-audit.md) | Enterprise-focused guardrails |
| Contribute with confidence | [Contributing guide](CONTRIBUTING.md) | Quality gates + PR expectations |

## Experience navigation (one-click)

### Governance & trust
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Support](SUPPORT.md)
- [License](LICENSE)
- [Commercial Licensing](COMMERCIAL_LICENSE.md)

### Engineering standards
- [Quality Playbook](QUALITY_PLAYBOOK.md)
- [Release Guide](RELEASE.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)

### Documentation hub
- [Docs Home](docs/index.md)
- [Repo Tour](docs/repo-tour.md)
- [Project Structure](docs/project-structure.md)
- [Security Docs](docs/security.md)
- [Release Process](docs/releasing.md)

## Why this repository exists

This project is designed for fast onboarding and high-confidence delivery:

- **Clear entry points** in [`src/sdetkit`](src/sdetkit)
- **Strong quality gates** across lint, format, type checks, tests, coverage, and docs
- **Modular internals** that are easy to import, test, and extend
- **Docs-first architecture** for fast navigation and contributor productivity

## 30-second orientation

1. Read this [README](README.md) for the quickest overview.
2. Open [docs/repo-tour.md](docs/repo-tour.md) for a visual repository map.
3. Use [docs/cli.md](docs/cli.md) + [docs/doctor.md](docs/doctor.md) for daily workflows.
4. Follow [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

## Quick start

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-test.txt -r requirements-docs.txt -e .
bash quality.sh cov
```

## Repository map

```text
src/sdetkit/              # package source: CLI + library modules
tests/                    # unit tests, behavior tests, mutation-test killers
docs/                     # mkdocs pages for usage, design, and process
scripts/                  # local helper scripts (check, env, bootstrap)
tools/                    # extra developer tooling + patch harness wrapper
```

## Core CLI commands

```bash
./.venv/bin/sdetkit --help
./.venv/bin/sdetkit doctor --all
./.venv/bin/sdetkit apiget https://example.com/api --expect dict
./.venv/bin/sdetkit repo audit --format text
./.venv/bin/sdetkit repo check . --profile enterprise --format json
./.venv/bin/python tools/patch_harness.py spec.json --check
```

## Maintenance

```bash
python -m sdetkit.maintenance --mode quick --format json
python -m sdetkit maintenance --mode full --fix --format md --out artifacts/maintenance.md
bash scripts/maintenance_ci.sh full true artifacts/maintenance
```

The maintenance engine emits a stable, versioned report schema (`ok`, `score`, `checks`, `recommendations`, `meta`) in JSON and Markdown formats so local runs and CI artifacts match.

## Developer workflow

```bash
# full quality gates
bash scripts/check.sh all

# alternative quality runner with coverage target
bash quality.sh cov

# convenience shell with .venv/bin on PATH
bash scripts/shell.sh
```

## Documentation index

- [docs/index.md](docs/index.md) — docs homepage
- [docs/repo-tour.md](docs/repo-tour.md) — visual orientation + role-based quick links
- [docs/project-structure.md](docs/project-structure.md) — architecture + file/folder map
- [docs/cli.md](docs/cli.md) — CLI command guide
- [docs/doctor.md](docs/doctor.md) — repository health diagnostics
- [docs/repo-audit.md](docs/repo-audit.md) — repo audit and repository hardening
- [docs/patch-harness.md](docs/patch-harness.md) — spec-driven patch harness usage
- [docs/security.md](docs/security.md) — security policies and notes
- [docs/releasing.md](docs/releasing.md) — release process

## Automation highlights

- Docs deployment: [.github/workflows/pages.yml](.github/workflows/pages.yml)
- Release workflow: [.github/workflows/release.yml](.github/workflows/release.yml)
- Version consistency guard: [.github/workflows/versioning.yml](.github/workflows/versioning.yml)
- PR quality feedback: [.github/workflows/pr-quality-comment.yml](.github/workflows/pr-quality-comment.yml)
- Security automation: CodeQL + scheduled secret scanning workflow (see [docs/security.md](docs/security.md))
- Weekly maintenance automation: [.github/workflows/weekly-maintenance.yml](.github/workflows/weekly-maintenance.yml)
- On-demand maintenance workflow: [.github/workflows/maintenance-on-demand.yml](.github/workflows/maintenance-on-demand.yml)
- Shared CI maintenance runner: [scripts/maintenance_ci.sh](scripts/maintenance_ci.sh)
- Dependency automation: Dependabot daily updates + safe auto-merge workflow for low-risk updates

## Contributing and support

- [Contributing Guide](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)
- [Support](SUPPORT.md)

## License

Free for personal/educational noncommercial use. Commercial use requires a paid license (see [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md)).
