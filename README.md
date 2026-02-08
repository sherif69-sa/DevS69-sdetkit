<div align="center">

# SDET Bootcamp (sdetkit)

Production-style SDET utilities + exercises (CLI tools, quality gates, and testable modules).

[![Quality](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/quality.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/quality.yml)
[![Pages](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/pages.yml)
[![Release](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/release.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/release.yml)
[![Mutation Tests](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/mutation-tests.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/mutation-tests.yml)
[![Security](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/security.yml)
[![Dependency Audit](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/dependency-audit.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/dependency-audit.yml)

[![Latest Release](https://img.shields.io/github/v/release/sherif69-sa/sdet_bootcamp?sort=semver)](https://github.com/sherif69-sa/sdet_bootcamp/releases)
[![License](https://img.shields.io/github/license/sherif69-sa/sdet_bootcamp)](LICENSE)

</div>

## What you get

- CLI tools:
  - `sdetkit kv` / `kvcli`: parse `key=value` input and output JSON
  - `sdetkit apiget` / `apigetcli`: fetch JSON with pagination/retries/timeouts
- SDET-friendly quality gates:
  - ruff (format + lint), mypy, pytest, coverage, mkdocs build
- Testable modules you can import:
  - `sdetkit.apiclient`, `sdetkit.netclient`, `sdetkit.atomicio`, `sdetkit.textutil`

## Quick start

```bash
cd ~/sdet_bootcamp
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-test.txt -r requirements-docs.txt -e .
bash scripts/check.sh all
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

## Repo docs

* Project structure: docs/project-structure.md
* Roadmap: docs/roadmap.md
* Contributing: docs/contributing.md

## Contributing

See CONTRIBUTING.md.

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
