# Releasing sdetkit

This project uses semantic versioning (`MAJOR.MINOR.PATCH`) and a tag-driven release workflow.

Current baseline release: **v1.0.0**.

## Version bump rules

- **PATCH** (`x.y.Z`): bug fixes, docs-only operational improvements, non-breaking internal changes.
- **MINOR** (`x.Y.z`): backward-compatible features.
- **MAJOR** (`X.y.z`): breaking public API or CLI behavior changes.

## Release checklist

1. Update `version` in `pyproject.toml`.
2. Add a matching version section to `CHANGELOG.md`.
3. Run local quality and packaging checks:

   ```bash
   pre-commit run -a
   bash quality.sh cov
   python -m build
   python -m twine check dist/*
   mkdocs build
   ```

4. Commit changes and open/merge a PR.
5. Create and push a signed tag: `vX.Y.Z`.
6. Confirm GitHub Actions release workflow succeeded.
7. Confirm artifacts were published to PyPI.

## CI release safeguards

Every PR validates packaging integrity with:

- `python -m build`
- `python -m twine check dist/*`
- wheel smoke install and CLI check (`sdetkit --help`)

The release workflow also verifies the tag matches `pyproject.toml` version.

## Publishing to PyPI

Publishing is handled by GitHub Actions in `.github/workflows/release.yml`.

- On tag push `v*.*.*`, artifacts are built and uploaded.
- Upload uses the configured `PYPI_API_TOKEN` secret.
- If no token is configured, packaging checks still run and release artifacts are generated.
