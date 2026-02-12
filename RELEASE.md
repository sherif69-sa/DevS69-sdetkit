# Release Process

This project follows semantic versioning and a reproducible release flow.

Current target: **v1.0.0 (stable)**.

## Versioning Policy

- `0.x`: fast iteration is allowed, but the patch-spec schema stays versioned (`spec_version`).
- `1.0+`: patch spec is stable; incompatible changes require a new schema version and deprecation window.

## Checklist

1. Ensure release metadata is finalized for `v1.0.0` (or next target):
   - `pyproject.toml` version
   - matching heading in `CHANGELOG.md`
   - any embedded fallback `tool_version` values used in reports/templates
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
