# Release Process

This project follows semantic versioning and a reproducible release flow.

## Versioning Policy

- `0.x`: fast iteration is allowed, but the patch-spec schema stays versioned (`spec_version`).
- `1.0+`: patch spec is stable; incompatible changes require a new schema version and deprecation window.

## Checklist

1. Update version in `pyproject.toml` and `CHANGELOG.md`.
2. Create a release tag `vX.Y.Z`.
3. Run release validation locally:
   - `python -m build`
   - `python -m twine check dist/*`
   - `python -m pip install dist/*.whl`
   - `sdetkit --help`
4. Push the tag.
5. Confirm GitHub Release workflow passed and artifacts are attached.
6. Confirm publish job uploaded to PyPI.
7. Verify Dependency Audit workflow is green for the release commit/tag.
8. (Optional) Generate and archive SBOM (`.github/workflows/sbom.yml`).
