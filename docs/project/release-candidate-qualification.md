# Release candidate qualification

This path proves repository and package readiness **before** a release tag exists and without publishing anything.

The workflow is `.github/workflows/release-candidate.yml`.

## What it proves

The workflow:

1. resolves the package version and checked-out source SHA;
2. validates the synthetic candidate tag `v<project.version>` against release metadata and the changelog;
3. runs the coverage and strict documentation gates;
4. builds the wheel and source distribution exactly once;
5. validates package metadata and wheel contents;
6. installs and exercises that exact wheel on Python 3.10, 3.11, and 3.12;
7. emits candidate, distribution-manifest, per-Python qualification, and final-verdict artifacts.

## What it cannot do

The workflow has read-only repository permissions. It does not request an OIDC token and does not:

- create or move a tag;
- publish to PyPI or TestPyPI;
- create a GitHub Release;
- attest a public release;
- mark external publishing settings as verified;
- authorize publication.

Every candidate status and verdict artifact contains:

```text
external_settings_verified=false
publish_authorized=false
publication_attempted=false
tag_created=false
```

## Run it

It runs automatically when relevant release surfaces change in a pull request and again when those changes reach `main`. A maintainer may also run **Release Candidate Qualification** manually from GitHub Actions.

Expected artifact names:

```text
release-candidate-distributions
release-candidate-qualification-py3.10
release-candidate-qualification-py3.11
release-candidate-qualification-py3.12
release-candidate-verdict
```

## Promotion boundary

A green qualification run is repository evidence, not publication proof. Before creating `v1.1.0`, a maintainer must independently verify:

1. the protected GitHub environment is named `pypi` and has the intended reviewers and deployment rules;
2. the PyPI Trusted Publisher is bound to owner `sherif69-sa`, repository `DevS69-sdetkit`, workflow `release.yml`, and environment `pypi`.

Only the tagged `.github/workflows/release.yml` path may request publishing authority. Public release completion still requires Trusted Publishing, attestations, public-index digest/install verification, and creation of the GitHub Release after PyPI verification.
