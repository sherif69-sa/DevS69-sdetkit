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
3. Generate post-release verification plan and confirm package install string before tagging:

   ```bash
   make release-verify-plan
   python scripts/release_verify_post_publish.py --assert-install-string
   ```

   This validates the canonical external install target (`pip install sdetkit==<version>`) and prints a deterministic verification plan maintainers can execute after publish.
4. Create and push the tag:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
5. Watch `.github/workflows/release.yml` complete.
6. Verify outcomes:
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

## Post-release verification (external-user perspective)

Run these in a clean shell after the release workflow shows a successful PyPI upload:

```bash
python -m venv .venv-release-verify
. .venv-release-verify/bin/activate
python -m pip install -U pip
python -m pip install sdetkit==X.Y.Z
python -m sdetkit --help
python -m pip show sdetkit
```

Success means:
- `pip install` resolves from default PyPI index without private index overrides.
- `python -m sdetkit --help` exits 0 and prints CLI usage.
- `pip show sdetkit` reports the expected version (`X.Y.Z`).

Also confirm:
- GitHub Release page for `vX.Y.Z` is present with generated notes and `dist/*` artifacts.
- PyPI project/version page exists and files include wheel + source tarball.
- The release workflow job includes a successful **Publish to PyPI** step (not skipped).

Only after all checks pass is it safe to claim public availability.

## Record public verification evidence

After completing external-user verification for a real release, add a short record to `docs/release-verification.md` using the page template.

Keep entries factual and minimal:
- exact released version
- exact install and validation commands run
- verifier environment (OS, Python, pip)
- success signals + links (PyPI version page and GitHub Release)
- support path if users cannot install

Do not add a verification entry unless the release was actually published and validated externally.

## Optional risk-reduction rehearsal (TestPyPI)

If maintainers want a dry run before the first real publish, run from local `dist/*` against TestPyPI manually with a separate token:

```bash
python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple sdetkit==X.Y.Z
```

This repository does not auto-publish to TestPyPI in CI; this path is an optional rehearsal only.

## Release checklist (required)

Before pushing a release tag, maintainers must complete this checklist:

- [ ] Version updated in `pyproject.toml`.
- [ ] Matching version heading added in `CHANGELOG.md`.
- [ ] `make release-preflight` completed successfully.
- [ ] Post-release verify plan generated and install string validated.
- [ ] Release tag `vX.Y.Z` pushed and workflow monitored to completion.
- [ ] External install verification completed before public availability claims.
