# Releasing sdetkit

This project uses semantic versioning and a tag-driven, fail-closed release workflow.

Current baseline release: **v1.0.3**.

## Version bump rules

- **PATCH** (`x.y.Z`): bug fixes, documentation-only operational improvements, and non-breaking internal changes.
- **MINOR** (`x.Y.z`): backward-compatible features.
- **MAJOR** (`X.y.z`): breaking public API, CLI, or artifact-contract changes.

## One-time publisher configuration

Production publishing requires:

- a protected GitHub environment named `pypi`;
- a PyPI Trusted Publisher bound to `sherif69-sa/DevS69-sdetkit`;
- workflow filename `.github/workflows/release.yml`;
- GitHub environment `pypi`.

The workflow uses OIDC and does not consume a long-lived PyPI API token. Missing publisher configuration causes publication to fail; it cannot produce a successful GitHub Release without a verified PyPI publication.

## Release checklist

1. Update `version` in `pyproject.toml`.
2. Add a matching version section to `CHANGELOG.md`.
3. Refresh current product-delta and release-candidate evidence.
4. Run local quality and packaging checks:

   ```bash
   python -m pre_commit run -a
   COV_FAIL_UNDER=95 bash quality.sh cov
   NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict
   python -m build
   python -m twine check dist/*
   python -m check_wheel_contents --ignore W009 dist/*.whl
   ```

5. Run release metadata preflight:

   ```bash
   make release-preflight
   make release-verify-plan
   python scripts/release_verify_post_publish.py --assert-install-string
   ```

6. Commit release metadata and merge only after required checks are green.
7. Create and push a signed tag: `vX.Y.Z`.
8. Review the exact source SHA and distribution manifest, then approve the protected `pypi` environment deployment.
9. Confirm the release workflow completed in order:
   - build once;
   - exact-wheel qualification on Python 3.10, 3.11, and 3.12;
   - GitHub provenance attestation;
   - PyPI Trusted Publishing and publish attestations;
   - public PyPI filename, digest, and installation verification;
   - GitHub Release creation.
10. Run an independent clean-environment verification:

    ```bash
    python -m venv .venv-release-verify
    . .venv-release-verify/bin/activate
    python -m pip install -U pip
    python -m pip install --index-url https://pypi.org/simple/ sdetkit==X.Y.Z
    python -m sdetkit --help
    python -m pip show sdetkit
    ```

## CI release safeguards

Every pull request validates packaging integrity with build, Twine, wheel-content, and isolated installed-wheel contracts.

The tag-only release workflow adds stronger controls:

- manual inputs are environment-bound and validated as `vX.Y.Z` before shell use;
- wheel and sdist are built once and recorded in a SHA-256 manifest;
- the exact wheel is qualified on every supported Python version;
- publish authority is protected behind the `pypi` environment;
- job-level `id-token: write` is limited to attestation and publication;
- PyPI filenames and SHA-256 digests must match the build manifest;
- public installation must pass before the GitHub Release is created;
- missing publication proof fails closed.

## Publishing boundary

Publishing is handled only by `.github/workflows/release.yml` using PyPI Trusted Publishing. The official PyPA action receives a short-lived OIDC credential and uploads attestations for the exact distributions.

The following are not publication proof:

- a successful build;
- a successful TestPyPI rehearsal;
- a pending `pypi` environment approval;
- a skipped or failed publish job;
- a GitHub artifact containing distributions;
- a local install from `dist/`.

## Record public verification evidence

After publication and independent verification, add a factual record to `docs/release-verification.md` with:

- exact version, tag, and source SHA;
- distribution hashes;
- exact validation commands;
- verifier OS, Python, and pip versions;
- PyPI and GitHub Release references;
- attestation status;
- support path if installation fails.

Do not add a public verification record until the release exists and clean-room verification has completed.

## Optional TestPyPI rehearsal

A TestPyPI rehearsal may use a separate Trusted Publisher and protected environment. It is intentionally separate from the production workflow and does not authorize a production release.
