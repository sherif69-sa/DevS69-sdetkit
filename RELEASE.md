# Release Process

This project follows semantic versioning and a reproducible release flow.

Current version is taken from `[project].version` in `pyproject.toml`.

Release tags must be `vX.Y.Z` and must match the package version. `CHANGELOG.md` must include a matching heading (for example: `## [X.Y.Z]` or `## vX.Y.Z`).

## Versioning Policy

- `0.x`: fast iteration is allowed, but the patch-spec schema stays versioned (`spec_version`).
- `1.0+`: patch spec is stable; incompatible changes require a new schema version and deprecation window.

## Release preconditions (before any tag push)

- Repository secret `PYPI_API_TOKEN` must be configured to enable PyPI upload.
- If `PYPI_API_TOKEN` is not configured, the release workflow still builds artifacts and creates a GitHub Release, but PyPI upload is skipped.
- The release workflow requires:
  - `pyproject.toml` `[project].version`
  - matching heading in `CHANGELOG.md`
  - tag in the form `vX.Y.Z` that matches version

## Maintainer path (first public release)

1. Finalize release metadata for the target version:
   - update `[project].version` in `pyproject.toml`
   - add matching heading in `CHANGELOG.md`
2. Run local preflight (single command):

   ```bash
   make release-preflight
   ```

   This runs release metadata validation, `doctor --release --skip clean_tree`, artifact build validation, and wheel smoke install.
3. Create and push the tag:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
4. Watch `.github/workflows/release.yml` complete.
5. Verify outcomes:
   - GitHub Release exists and includes `dist/*` artifacts.
   - PyPI upload occurred only if `PYPI_API_TOKEN` secret is configured.
   - Dependency/security workflows are green for the same commit/tag.

## Workflow triggers

- **Tag push**: automatic for tags matching `v*.*.*`.
- **Manual dispatch**: `workflow_dispatch` with an existing `tag` input.

The workflow performs:
1. release metadata preflight (`scripts/release_preflight.py`)
2. tag/version consistency check (`scripts/check_release_tag_version.py`)
3. quality gates + coverage
4. artifact build + metadata checks + wheel smoke test
5. conditional PyPI upload
6. provenance attestation + GitHub Release creation

## What not to claim before publish is real

Do not claim public PyPI availability until:
- the release workflow succeeded,
- the PyPI upload step ran (not skipped), and
- install from PyPI is verified externally.
