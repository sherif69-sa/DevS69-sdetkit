# Dependency radar

`sdetkit kits radar` shows where the dependencies your `pyproject.toml` declares are used, which ones are hottest, and what to validate first when one of them changes.

```bash
python -m sdetkit kits radar
python -m sdetkit kits radar httpx --format json
python -m sdetkit kits radar --impact-area runtime-core
python -m sdetkit kits radar --repo-usage-tier hot-path --limit 10
python -m sdetkit kits radar --repo-root ../service
```

On this repository:

```text
dependency radar: 18 declared, 2 runtime, 4 hot-path, 18 locked (uv.lock)
- Hot-path dependencies: 4
- Runtime dependencies: 2
- Runtime dependencies never imported: 0
- Declared but not in the lockfile: 0
hotspots:
  pytest: 135 files (133 tests) -> python -m sdetkit gate fast --only pytest
  httpx: 39 files (35 tests) -> python -m sdetkit gate fast --only pytest
  pyyaml: 16 files (15 tests) -> python -m sdetkit gate fast --only pytest
```

## Where the numbers come from

- **Declared dependencies:** `[project].dependencies` (the `runtime` group), each `[project.optional-dependencies]` extra, and each PEP 735 `[dependency-groups]` group in `pyproject.toml`.
- **Locked versions:** `uv.lock`, `poetry.lock`, `pdm.lock`, `Pipfile.lock` or pinned requirement files, read the same way as by the security gate.
- **Usage:** every `import` and `from … import` in the repository's own Python files, read with Python's parser. A comment or a string that mentions a package does not count.
  - Skipped: `.venv`, `build`, `node_modules` and similar folders, `fixtures` folders, and nested projects (folders with their own `pyproject.toml` or `setup.py`).
  - Import names come from the installed distributions where available, so `pyyaml` is found as `import yaml`.
- **Tiers:** `hot-path` means 3 or more files import the package, `edge` means 1 or none, and `balanced` is everything in between.

## What it emits

| Field | Meaning |
| --- | --- |
| `headline_metrics` | Declared, runtime, hot-path and locked package counts, and the number of files scanned. |
| `dashboard_cards` | Hot-path dependencies, runtime dependencies, runtime dependencies never imported, and (with a lockfile) dependencies missing from it. |
| `hotspots` | The matching packages with the most importing files, each with its narrowest validation command. |
| `watchlists` | `runtime_core`, `hot_path`, `unused_runtime` and `not_locked` package names. |
| `maintenance_lanes` | What to run next: the top hotspot's validation and route map, then `intelligence upgrade-audit`. |
| `unparsed_files` | Files that could not be parsed, so their imports were not counted. |

## Filters

- `query`: package names, dependency groups, or text in a usage path (`httpx`, `docs`, `cli.py`); several words match any of them.
- `--impact-area`: a dependency group. `runtime-core` (or `runtime`) means `[project].dependencies`; `all` (default) means every group.
- `--repo-usage-tier`: `hot-path`, `edge`, or `balanced` (default, no tier filter).

To get the validation command for each package, use the [validation route map](validation-route-map.md).
