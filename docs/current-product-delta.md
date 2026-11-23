# Current product delta

Contract: [`docs/contracts/current-product-delta.v1.json`](contracts/current-product-delta.v1.json)

## Release truth

| Surface | Current truth |
|---|---|
| Published package | `sdetkit==2.0.0` |
| Repository package metadata | `2.0.0` |
| Release state | 2.0.0 published on 2026-11-16 |
| Last published source SHA | `5b2b409910406cb7e637b7116436552824107e38` (`v2.0.0`) |

The release verification log records the published 2.0.0 distributions and clean installation. Python 3.11 or newer is required. Development on `main` continues after the release; use a tagged release when you need a fixed version.

## Released 2.0.0 baseline

The following capability groups formed the 2.0.0 baseline:

- **Release-confidence CLI:** about 40 commands in four groups instead of 191; `gate fast` in any repository through one repository model; one `sdetkit.verdict.v1` verdict across the gate, mission control, the release room and the remediation loop.
- **Local remediation loop:** `diagnose run` from saved CI logs or the latest failing gate run, a fix proved in a throwaway copy, decision cards, and decisions recorded with `diagnose decide`.
- **Trajectory and memory:** RepoMemory accumulates every attempt and feeds proven fix patterns to the patch scorer.
- **First-run reliability:** clean-tree checks ignore SDETKit's own outputs, one lockfile detector recognises uv, Poetry, PDM and Pipenv, and `repo` subcommands accept any repository root.
- **Checks in the project's own environment:** `gate fast` runs ruff, mypy and pytest with the repository's own interpreter and the way its pre-commit hooks and `tox.ini` run them, and reports failures that come from the environment as `NOT_RUN` with the setup command. The [external repository proof](external-repo-proof.md) shows it on seven open-source projects.

2.0.0 removes commands, flags, modules and console scripts; the upgrade notes are in [CHANGELOG.md](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/CHANGELOG.md).

The stable first path is unchanged:

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

## Release verification

Version 2.0.0 has been tagged, published and independently verified. See the [public release verification log](release-verification.md) for the exact source SHA, distributions and commands. This does not qualify later changes on `main` as part of that release.

## Authority boundary

This document does not authorize automated patching, merging, security dismissal, future publication, or semantic-equivalence claims.
