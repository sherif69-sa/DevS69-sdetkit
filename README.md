<div align="center">

# SDET Bootcamp (sdetkit)

Production-style SDET utilities + bootcamp exercises: CLI tools, quality gates, and testable modules.

[![CI](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/ci.yml)
[![Quality](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/quality.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/quality.yml)
[![Mutation Tests](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/mutation-tests.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/mutation-tests.yml)
[![Security](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/security.yml)
[![Dependency Audit](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/dependency-audit.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/dependency-audit.yml)
[![Pages](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/pages.yml)
[![Release](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/release.yml/badge.svg?event=release)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/release.yml)
[![Dependabot Updates](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/dependabot/dependabot-updates)

[![Latest Release](https://img.shields.io/github/v/release/sherif69-sa/sdet_bootcamp?sort=semver)](https://github.com/sherif69-sa/sdet_bootcamp/releases)
[![License](https://img.shields.io/github/license/sherif69-sa/sdet_bootcamp)](LICENSE)

</div>

<!-- Optional: add a banner image at docs/assets/banner.png and link it here -->
<!-- ![Banner](docs/assets/banner.png) -->

## What you get

- CLI tools:
  - `sdetkit kv` / `kvcli`: parse `key=value` input and output JSON
  - `sdetkit apiget` / `apigetcli`: fetch JSON with pagination/retries/timeouts
  - `sdetkit doctor`: repo health checks, venv/pyproject validation, score, and actionable recommendations
  - `sdetkit patch`: deterministic spec-driven edits with strict --check (plus legacy tools/patch_harness.py wrapper)
- Quality gates (local + CI):
  - ruff (lint + format), mypy, pytest, coverage gate, docs build
- Importable modules (easy to unit test):
  - `sdetkit.apiclient`, `sdetkit.netclient`, `sdetkit.atomicio`, `sdetkit.textutil`

## Quick start

```bash
cd ~/sdet_bootcamp
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-test.txt -r requirements-docs.txt -e .
bash quality.sh cov
````

## CLI

```bash
./.venv/bin/sdetkit --help
./.venv/bin/python -m sdetkit --help

./.venv/bin/kvcli --help
./.venv/bin/apigetcli --help
```

Tip: open a shell with venv tools on PATH:

```bash
bash scripts/shell.sh
apigetcli --help
kvcli --help
```

Or set PATH for the current shell:

```bash
source scripts/env.sh
apigetcli --help
kvcli --help
```

## Quick examples

apiget:

```bash
./.venv/bin/sdetkit apiget https://example.com/api --expect dict
./.venv/bin/sdetkit apiget https://example.com/items --expect list --paginate --max-pages 50
./.venv/bin/sdetkit apiget https://example.com/items --expect any --header "X-Request-ID: abc-123"
```

doctor:

```bash
./.venv/bin/sdetkit doctor --ascii
./.venv/bin/sdetkit doctor --all
./.venv/bin/sdetkit doctor --all --json
```

patch_harness:

```bash
./.venv/bin/python tools/patch_harness.py spec.json --check
./.venv/bin/python tools/patch_harness.py spec.json --dry-run
./.venv/bin/python tools/patch_harness.py spec.json
```

## Repo docs

* CLI: docs/cli.md
* Doctor: docs/doctor.md
* Patch harness: docs/patch-harness.md
* Project structure: docs/project-structure.md
* Roadmap: docs/roadmap.md
* Contributing: docs/contributing.md

## Contributing

See CONTRIBUTING.md.

## Automation

- Docs deploy: `.github/workflows/pages.yml` builds mkdocs on every push to `main` and deploys GitHub Pages.
- Release: `.github/workflows/release.yml` publishes built artifacts on `vX.Y.Z` tags.
- Versioning guard: `.github/workflows/versioning.yml` validates that `CHANGELOG.md` contains the active package version.
- PR quality feedback: `.github/workflows/pr-quality-comment.yml` runs `quality.sh cov` on PR updates and comments the result.


## License

MIT. See LICENSE.

## Development

* Install deps:

  * `pip install -r requirements-test.txt -r requirements-docs.txt`
* Run:

  * `bash ci.sh`
  * `bash quality.sh`
* Enable git hooks:

  * `pip install pre-commit && pre-commit install`

## Release

* Releases are triggered by pushing an annotated tag like vX.Y.Z.
* The tag version must exactly match pyproject.toml [project].version (enforced in CI).
* After releasing X.Y.Z, bump main to the next version before creating the next tag.

Example:

* update pyproject.toml version
* git tag -a vX.Y.Z -m "vX.Y.Z"
* git push origin vX.Y.Z

## Development (local)

* Setup (creates .venv and installs deps):

  * bash scripts/bootstrap.sh
* Run quality gates:

  * bash quality.sh cov
* Or use Make targets:

  * make cov
