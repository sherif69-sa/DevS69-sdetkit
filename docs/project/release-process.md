# Release Process

This project follows semantic versioning and a reproducible, fail-closed release flow.

Current version is taken from `[project].version` in `pyproject.toml`.

Release tags must be `vX.Y.Z` and must match the package version. `CHANGELOG.md` must include a matching heading, for example `## [X.Y.Z]` or `## vX.Y.Z`.

## Versioning policy

- `0.x`: fast iteration is allowed, but public schemas remain versioned.
- `1.0+`: incompatible public API, CLI, or artifact-contract changes require a new version and an explicit compatibility plan.

## Release preconditions

Before any release tag is pushed:

1. Configure a protected GitHub environment named `pypi`.
2. Configure the PyPI project `sdetkit` with a GitHub Actions Trusted Publisher for:
   - owner: `sherif69-sa`
   - repository: `DevS69-sdetkit`
   - workflow: `release.yml`
   - environment: `pypi`
3. Add required reviewers and deployment protection to the GitHub `pypi` environment.
4. Do not configure or rely on a long-lived `PYPI_API_TOKEN` for this workflow.
5. Confirm:
   - `[project].version` is final;
   - `CHANGELOG.md` has a matching release heading;
   - the release tag is `vX.Y.Z` and matches the package version;
   - current main and all required release-readiness PRs are green.

Missing or incorrect Trusted Publisher configuration is a release blocker. The workflow does not silently skip PyPI publication and continue to GitHub Release creation.

Manual dispatch accepts only an existing tag matching `vX.Y.Z`. The input is passed through the environment, validated before shell use, and never interpolated directly into a shell script.

## Maintainer path

1. Finalize release metadata:
   - update `[project].version` in `pyproject.toml`;
   - add a matching section in `CHANGELOG.md`;
   - refresh release-candidate adoption and quality evidence.
2. Run local preflight:

   ```bash
   make release-preflight
   ```

3. Generate the post-release verification plan and validate the install string:

   ```bash
   make release-verify-plan
   python scripts/release_verify_post_publish.py --assert-install-string
   ```

4. Run focused repository proof:

   ```bash
   python -m pre_commit run -a
   COV_FAIL_UNDER=95 bash quality.sh cov
   NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict
   python -m build
   python -m twine check dist/*
   python -m check_wheel_contents --ignore W009 dist/*.whl
   ```

5. Merge the release metadata PR only after required checks are green.
6. Create and push the signed tag:

   ```bash
   git tag -s vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```

7. Approve the protected `pypi` environment deployment only after reviewing the exact tag, source SHA, distribution manifest, and Python-version qualification jobs.
8. Watch `.github/workflows/release.yml` complete.
9. Confirm the public PyPI metadata and distribution digests match the build manifest.
10. Confirm the public PyPI install verification succeeded.
11. Confirm the GitHub Release was created only after PyPI verification.

## Workflow contract

The release workflow performs these ordered jobs:

1. **Build**
   - validate the requested tag before shell use;
   - check out the existing tag;
   - validate tag, package version, and changelog metadata;
   - run coverage and strict docs proof;
   - build the wheel and sdist exactly once;
   - record SHA-256 digests in a distribution manifest.
2. **Qualify exact wheel**
   - download the immutable build artifact;
   - install and exercise the exact wheel on Python 3.10, 3.11, and 3.12;
   - run installed-wheel and canonical command contracts.
3. **Attest**
   - attach GitHub build provenance to the qualified distributions.
4. **Publish to PyPI**
   - enter the protected `pypi` environment;
   - request a short-lived OIDC credential through Trusted Publishing;
   - publish the same qualified files;
   - generate PyPI publish attestations.
5. **Verify public publication**
   - wait for the exact version to appear on PyPI with bounded retries;
   - compare every published filename and SHA-256 digest with the build manifest;
   - install the exact version from the public PyPI index and verify metadata and CLI availability.
6. **Create GitHub Release**
   - create the GitHub Release only after successful PyPI verification;
   - attach the exact published distributions and release diagnostics.

No job rebuilds the distributions after the build job.

## What not to claim

Do not claim public availability, successful publication, attestation, or release completion until:

- the exact-wheel qualification matrix is green;
- Trusted Publishing completed successfully;
- the public PyPI digest and install verification is green;
- the GitHub Release exists and contains the same distribution files;
- the tag, source SHA, and distribution manifest agree.

A prediction, workflow configuration, pending environment approval, or successful local build is not publication proof.

## Post-release verification

The workflow performs automated public-index verification. A maintainer should also verify from a separate clean environment:

```bash
python -m venv .venv-release-verify
. .venv-release-verify/bin/activate
python -m pip install -U pip
python -m pip install --index-url https://pypi.org/simple/ sdetkit==X.Y.Z
python -m sdetkit --help
python -m pip show sdetkit
```

Success means:

- the package resolves from public PyPI without a private index override;
- the installed version equals `X.Y.Z`;
- the CLI starts successfully;
- PyPI contains the wheel and sdist with the expected hashes;
- PyPI publish attestations are present;
- the GitHub Release contains the exact qualified artifacts.

## Record public verification evidence

After a real release is published and externally validated, add a factual record to `docs/release-verification.md` containing:

- exact version, tag, and source SHA;
- exact install and validation commands;
- verifier OS, Python, and pip versions;
- distribution hashes;
- PyPI and GitHub Release references;
- attestation verification result;
- support path for failed installation.

Do not add a release-verification entry before publication and clean-room validation actually complete.

## Optional TestPyPI rehearsal

A TestPyPI rehearsal must use a separate, explicitly configured Trusted Publisher and protected environment. It is not part of the default production release workflow and must not reuse production release authority.

## Required release checklist

- [ ] Version updated in `pyproject.toml`.
- [ ] Matching version heading added in `CHANGELOG.md`.
- [ ] Current product-delta and release-candidate evidence reviewed.
- [ ] `make release-preflight` completed successfully.
- [ ] Full quality, package, and docs proof completed.
- [ ] GitHub `pypi` environment protection verified.
- [ ] PyPI Trusted Publisher configuration verified.
- [ ] Signed tag `vX.Y.Z` pushed.
- [ ] Exact wheel qualified on Python 3.10, 3.11, and 3.12.
- [ ] Trusted Publishing and attestations succeeded.
- [ ] Public PyPI digest and installation verification succeeded.
- [ ] GitHub Release created after PyPI verification.
- [ ] External verification record added only after proof.
