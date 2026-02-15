# Monorepo + multi-project support

`sdetkit` supports deterministic multi-project audits from a single repository root.

## Manifest formats

Preferred file: `.sdetkit/projects.toml`.
Fallback: `pyproject.toml` with `[tool.sdetkit.projects]`.

If you prefer not to maintain explicit `[[project]]` entries, you can enable autodiscovery
from `pyproject.toml`:
Autodiscovery reads project names from `[project].name` (PEP 621) and also supports
`[tool.poetry].name`, `[tool.pdm].name`, and `[tool.hatch.metadata].name` for
legacy or non-PEP-621 projects.


```toml
[tool.sdetkit.projects]
autodiscover = true
autodiscover_roots = ["services", "libs"]
```

`autodiscover_roots` accepts a string list or comma-separated string.
When `autodiscover = true` is combined with explicit `[[project]]` entries,
manifest projects are kept first and autodiscovered projects are appended.
Duplicate names/roots are deduplicated in favor of the explicit manifest entry.

```toml
[[project]]
name = "api"
root = "services/api"
config = "services/api/pyproject.toml"
profile = "enterprise"
packs = ["core", "security"]
baseline = "services/api/.sdetkit/audit-baseline.json"
exclude = ["docs/*", "generated/*"]

[[project]]
name = "core"
root = "libs/core"
packs = "core,security"
```

## Commands

- List discovered projects:
  - `sdetkit repo projects list .`
  - `sdetkit repo projects list . --json`
- Aggregate audit:
  - `sdetkit repo audit . --all-projects`
  - `sdetkit repo audit . --all-projects --format json`
  - `sdetkit repo audit . --all-projects --format sarif`
- Fix-audit targeting:
  - `sdetkit repo fix-audit . --project api --apply`
  - `sdetkit repo fix-audit . --all-projects --dry-run`

## Aggregation behavior

- Project discovery is deterministic (manifest order).
- `--sort` switches to alphabetical project ordering.
- JSON aggregate schema: `sdetkit.audit.aggregate.v1`.
- SARIF output emits one SARIF file with separate `runs` per project.
- Baseline default per project root is `.sdetkit/audit-baseline.json`.

## Precedence

- Defaults < manifest values < project config < CLI flags.
- Project config is loaded from each project root (or manifest `config` path).
- CLI flags always win for profile, fail-on, packs, excludes, and baseline.

## Safety and determinism

- No network calls are used.
- Paths in findings and SARIF are normalized to relative POSIX style.
- `fix-audit` writes only under each selected project root.
