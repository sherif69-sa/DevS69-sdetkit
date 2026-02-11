# Project structure

This page is the quickest way to understand **where things are** and **where to start reading**.

## High-level layout

```text
.
├── src/sdetkit/     # application + library code
├── tests/           # automated tests
├── docs/            # mkdocs site pages
├── scripts/         # developer shell/check/bootstrap helpers
├── tools/           # extra tooling (including patch harness wrapper)
├── pyproject.toml   # package metadata + tool configuration
├── quality.sh       # local quality runner
└── mkdocs.yml       # documentation site config
```

## What to read first (by role)

| If you are... | Start here | Then read |
|---|---|---|
| New contributor | `README.md` | `CONTRIBUTING.md`, `docs/project-structure.md` |
| CLI user | `docs/cli.md` | `docs/doctor.md`, `docs/repo-audit.md` |
| Maintainer | `scripts/check.sh` | `quality.sh`, `noxfile.py`, `Makefile` |
| Release owner | `RELEASE.md` | `docs/releasing.md`, `CHANGELOG.md` |

## Key source modules (`src/sdetkit/`)

- `cli.py` — top-level command router
- `_entrypoints.py` — console script entrypoints (`kvcli`, `apigetcli`)
- `__main__.py` — `python -m sdetkit` launcher
- `apiclient.py` — high-level request operations
- `netclient.py` — network utilities (pagination/retries/breaker behavior)
- `doctor.py` — diagnostics, scoring, and recommendations
- `repo.py` — repository audit and policy checks
- `patch.py` — deterministic patch features
- `atomicio.py` — safe atomic file IO helpers
- `textutil.py` — small text helpers

## Supporting directories

- `tests/` — feature tests, CLI tests, module unit tests, mutation-test killer tests
- `scripts/` — one-command workflows:
  - `check.sh` (fmt/lint/types/tests/coverage/docs/all)
  - `bootstrap.sh` (create local environment + install dependencies)
  - `env.sh` / `shell.sh` (venv PATH convenience)
- `docs/` — user and maintainer documentation published via MkDocs
- `tools/` — additional helper scripts for local development

## Repo hygiene rules of thumb

- Keep top-level files focused on project-level workflows and policy.
- Prefer adding technical detail under `docs/` rather than expanding root-level markdown files indefinitely.
- Add new runtime code to `src/sdetkit/`; add tests under `tests/` with matching scope.
- Keep scripts composable and CI-compatible (`scripts/` + `quality.sh`).
