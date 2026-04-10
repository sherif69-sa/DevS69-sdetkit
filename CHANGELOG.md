## Unreleased

- release-confidence operating loop polish: added machine-readable public command surface enforcement, pre-merge changed-files strict gate, unified CI summary artifact, weekly KPI pack workflow (`sdetkit kpi-report`), and lazy root CLI command routing with legacy namespace support.
- dependency upgrades: raised `twilio` floor to `>=9.10.4,<10` and aligned `tomli` to `2.4.1` across requirements and lock manifests.
- add GHAS alert SLA + metrics export bots, wire them into maintenance coverage checks, and refresh GHAS automation docs.
- add Name 86 launch readiness closeout lane command, docs, checks, and tests (`name86-launch-readiness-closeout`).
- upgrade audit: parse modern `pyproject.toml` `[dependency-groups]` declarations, including `{include-group = "..."}` expansions.

# Changelog
## [1.0.2]

- Packaging: modernize license metadata.


## v1.0.1
- CI gate: run `sdetkit doctor --all` and `sdetkit repo check --profile enterprise` on every PR.

## v1.0.0
- Enterprise hardening: GitHub Actions pinned to commit SHAs.
- Dependency hygiene: requirements pinned and lockfiles added.
- Repo init/apply reliability: tolerate non-UTF-8 preset template files.
- Repo cleanliness: ignore local SDETKit workspace and docs build output.
- feat: add `name89-governance-scale-closeout` with strict closeout checks, pack emission, and execution evidence lane.
