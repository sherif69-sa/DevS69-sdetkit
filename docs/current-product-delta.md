# Current product delta

Contract: [`docs/contracts/current-product-delta.v1.json`](contracts/current-product-delta.v1.json)

## Release truth

| Surface | Current truth |
|---|---|
| Published package | `sdetkit==1.2.0` |
| Repository package metadata | `2.0.0` |
| Release state | 2.0.0 candidate scope established; not yet qualified, tagged or published |
| Last published source SHA | `5165a82f8cd2ab3ce6be29737a2afdad58ea85a5` (`v1.2.0`) |

The README and installation documentation stay pinned to `sdetkit==1.2.0` until 2.0.0 is published and independently verified. The 1.2.0 distribution hashes, clean public installation and GitHub Release are recorded in the [public release verification log](release-verification.md).

## Main-only scope (2.0.0 candidate)

These capabilities are on `main` and not in the published wheel:

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

## Release gates

The 2.0.0 release gates still open:

1. merge the release-truth candidate metadata;
2. freeze and qualify the exact 2.0.0 candidate SHA;
3. verify the protected `pypi` environment and Trusted Publisher;
4. create the immutable signed `v2.0.0` tag;
5. publish and verify the exact distributions;
6. record post-release public evidence.

## Authority boundary

This document does not authorize automated patching, merging, security dismissal, future publication, or semantic-equivalence claims.
