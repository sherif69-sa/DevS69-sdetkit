<div align="center">

# SDET Bootcamp (sdetkit)

Production-style SDET toolkit and exercises with a strong focus on **clarity**, **quality gates**, and **testable design**.

[![CI](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/ci.yml)
[![Quality](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/quality.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/quality.yml)
[![Mutation Tests](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/mutation-tests.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/mutation-tests.yml)
[![Security](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/security.yml)
[![Dependency Audit](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/dependency-audit.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/dependency-audit.yml)
[![Pages](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/pages.yml)

[![Latest Release](https://img.shields.io/github/v/release/sherif69-sa/sdet_bootcamp?sort=semver)](https://github.com/sherif69-sa/sdet_bootcamp/releases)
[![License](https://img.shields.io/github/license/sherif69-sa/sdet_bootcamp)](LICENSE)

</div>

## 🚀 Experience hub (start here)

Pick the path that matches what you want to do right now:

| Goal | Open this | Why it helps |
|---|---|---|
| Get running in minutes | [Quick start](#quick-start) | Fast environment setup + first quality run |
| Learn the repo quickly | [Repo tour](docs/repo-tour.md) | Visual orientation map + role-based walkthrough |
| Use the CLI productively | [CLI guide](docs/cli.md) | Practical command examples |
| Check repo health | [Doctor docs](docs/doctor.md) | Diagnostics and recommendations |
| Run safe repo checks and fixes | [Repo audit](docs/repo-audit.md) | Enterprise-focused safety profile |
| Contribute confidently | [Contributing guide](CONTRIBUTING.md) | Branching, quality gates, and expectations |

> 🌐 Prefer a polished docs UI? Open the docs site via **GitHub Pages** from the workflow badge above or build it locally with `mkdocs serve`.

## Why this repo exists

This repo is designed to be easy to navigate for new contributors and practical for daily engineering work:

- **Clear entry points** (`sdetkit`, `kvcli`, `apigetcli`)
- **Strong quality gates** (lint, format, type checks, tests, coverage, docs)
- **Modular internals** you can import and test independently
- **Docs-first navigation** so you can quickly find what to read next

## 30-second orientation

1. Start with **this README** for setup and command snippets.
2. Jump to **[`docs/repo-tour.md`](docs/repo-tour.md)** for a role-based navigation map.
3. Use **[`docs/cli.md`](docs/cli.md)** and **[`docs/doctor.md`](docs/doctor.md)** for daily command usage.
4. Check **[`CONTRIBUTING.md`](CONTRIBUTING.md)** before opening a pull request.

## Quick start

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-test.txt -r requirements-docs.txt -e .
bash quality.sh cov
```

## Repo map (what lives where)

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
./.venv/bin/sdetkit repo check . --profile enterprise --format json
./.venv/bin/python tools/patch_harness.py spec.json --check
```

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

- `docs/index.md` — docs homepage
- `docs/repo-tour.md` — visual orientation + role-based quick links
- `docs/project-structure.md` — architecture + file/folder map
- `docs/cli.md` — CLI command guide
- `docs/doctor.md` — repository health diagnostics
- `docs/repo-audit.md` — repo audit and safe fixes
- `docs/patch-harness.md` — spec-driven patch harness usage
- `docs/security.md` — security policies and notes
- `docs/releasing.md` — release process

## Automation highlights

- Docs deployment: `.github/workflows/pages.yml`
- Release workflow: `.github/workflows/release.yml`
- Version consistency guard: `.github/workflows/versioning.yml`
- PR quality feedback: `.github/workflows/pr-quality-comment.yml`

## Contributing and support

- Contributing guide: `CONTRIBUTING.md`
- Code of conduct: `CODE_OF_CONDUCT.md`
- Security policy: `SECURITY.md`
- Support notes: `SUPPORT.md`

## License

MIT. See `LICENSE`.
