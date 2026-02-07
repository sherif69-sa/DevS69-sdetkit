<div align="center">

# SDET Bootcamp (sdetkit)

Production-style SDET utilities + exercises (CLI tools, quality gates, and testable modules).

[![Quality](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/quality.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/quality.yml)
[![Pages](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/pages.yml)
[![Release](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/release.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/release.yml)
[![Mutation Tests](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/mutmut.yml/badge.svg?branch=main)](https://github.com/sherif69-sa/sdet_bootcamp/actions/workflows/mutmut.yml)

[![Latest Release](https://img.shields.io/github/v/release/sherif69-sa/sdet_bootcamp?sort=semver)](https://github.com/sherif69-sa/sdet_bootcamp/releases)
[![License](https://img.shields.io/github/license/sherif69-sa/sdet_bootcamp)](LICENSE)

</div>

## What you get

- **CLI tools**
  - `sdetkit kv` / `kvcli`: parse `key=value` input and output JSON
  - `sdetkit apiget` / `apigetcli`: fetch JSON with pagination/retries/timeouts
- **Importable modules**
  - `sdetkit.atomicio`: atomic write helper
  - `sdetkit.apiclient`: JSON fetch helpers (sync + async)
  - `sdetkit.textutil`: parsing helpers

## Quickstart

> Tip: you don't need to activate the venv. Use `.venv/bin/...`.

### One-time setup

```bash
cd ~/sdet_bootcamp
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-test.txt -r requirements-docs.txt -e .
````

### Daily commands

```bash
./.venv/bin/python -m pytest
bash scripts/check.sh all
```

## CLI usage

```bash
./.venv/bin/sdetkit --help
./.venv/bin/python -m sdetkit --help

./.venv/bin/kvcli --help
./.venv/bin/apigetcli --help
```

## Optional: shell with venv tools on PATH (no activate)

```bash
cd ~/sdet_bootcamp
bash scripts/shell.sh
# Now you can run:
#   apigetcli --help
#   kvcli --help
```

## License

MIT. See `LICENSE`.
