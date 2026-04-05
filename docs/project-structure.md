# Project structure

This page is the quickest way to understand **where things are**, **where new files should go**, and **which paths matter most first**.

## High-level layout

```text
.
├── .github/                 # CI, issue templates, automation workflows
├── .sdetkit/                # repo-local generated outputs and automation assets
├── artifacts/               # generated platform-problem artifacts and snapshots
├── docs/                    # MkDocs site pages
├── examples/                # sample inputs, outputs, and runnable examples
├── plans/                   # planning artifacts and working plans
├── scripts/                 # developer shell/check/bootstrap helpers
├── src/sdetkit/             # application + library code
├── templates/               # reusable templates and scaffolds
├── tests/                   # automated tests
├── tools/                   # extra tooling helpers
├── pyproject.toml           # package metadata + tool configuration
├── quality.sh               # local quality runner
├── README.md                # top-level product and repo entrypoint
└── mkdocs.yml               # documentation site config
```

## What to read first (by role)

| If you are... | Start here | Then read |
| --- | --- | --- |
| New contributor | `README.md` | `CONTRIBUTING.md`, `docs/project-structure.md` |
| CLI user | `docs/cli.md` | `docs/doctor.md`, `docs/repo-audit.md` |
| Maintainer | `quality.sh` | `scripts/check.sh`, `noxfile.py`, `Makefile` |
| Release owner | `RELEASE.md` | `docs/releasing.md`, `CHANGELOG.md` |
| Docs editor | `docs/index.md` | `mkdocs.yml`, `docs/contributing.md` |

## Root directory guide

The repository root should stay reserved for **project-wide entrypoints and policy**.

### Keep at the root

- project entry docs such as `README.md`, `CONTRIBUTING.md`, `RELEASE.md`, and `ROADMAP.md`
- project-wide policy and trust files such as `SECURITY.md`, `SUPPORT.md`, and `CODE_OF_CONDUCT.md`
- package/build configuration such as `pyproject.toml`, `mkdocs.yml`, `poetry.lock`, and `noxfile.py`
- top-level workflow runners such as `quality.sh`, `ci.sh`, `premium-gate.sh`, and `security.sh`

### Prefer subdirectories for everything else

| Content type | Preferred location |
| --- | --- |
| Runtime Python code | `src/sdetkit/` |
| Tests and fixtures | `tests/` |
| Long-form documentation | `docs/` |
| Examples and sample payloads | `examples/` |
| Reusable templates | `templates/` |
| Generated outputs/evidence | `.sdetkit/out/` or `artifacts/` |
| One-off helper scripts | `scripts/` or `tools/` |
| Planning material | `plans/` |

## Placement rules of thumb

1. Add a **new top-level file only** if it affects the entire project.
2. Add **new code** under `src/sdetkit/` and mirror its coverage in `tests/`.
3. Add **deep explanations** under `docs/` and link from `README.md` instead of expanding root docs forever.
4. Put **generated content** in `.sdetkit/out/` or `artifacts/`, not beside hand-maintained source files.
5. Put **templates/examples** in `templates/` and `examples/`, not mixed with production code.

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

- `tests/` — feature tests, CLI tests, module unit tests, and mutation-test killer tests
- `scripts/` — one-command workflows such as:
  - `check.sh` (fmt/lint/types/tests/coverage/docs/all)
  - `bootstrap.sh` (create local environment + install dependencies)
  - `env.sh` / `shell.sh` (venv PATH convenience)
- `docs/` — user and maintainer documentation published via MkDocs
- `examples/` — sample profiles, example payloads, and walkthrough data
- `templates/` — reusable scaffolding and authoring helpers
- `tools/` — additional helper scripts for local development
- `.github/` — Actions workflows, templates, and GitHub automation policy

## Repo hygiene checklist

Use this before introducing a new file or folder:

- Is this file **project-wide**? If not, keep it out of the root.
- Is this file **written by humans**? If not, prefer `.sdetkit/out/` or `artifacts/`.
- Is this content **documentation**? If yes, prefer `docs/`.
- Is this content **an example/template**? If yes, prefer `examples/` or `templates/`.
- Can the change be explained by linking from an existing page instead of adding another root file?


## Repository cleanup policy

For concrete placement standards, naming guidance, and a repeatable hygiene checklist, see [`docs/repo-cleanup-plan.md`](repo-cleanup-plan.md).
