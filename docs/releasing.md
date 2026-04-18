# Releasing sdetkit

This project uses semantic versioning (`MAJOR.MINOR.PATCH`) and a tag-driven release workflow.

Current baseline release: **v1.0.2**.

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
   NO_MKDOCS_2_WARNING=1 python -m mkdocs build -q
   ```

4. Commit changes and open/merge a PR.
5. Create and push a signed tag: `vX.Y.Z`.
6. Confirm GitHub Actions release workflow succeeded.
7. Confirm artifacts were published to PyPI (workflow step must be successful, not skipped).
8. Run external-user verification in a clean virtual environment:

   ```bash
   python -m venv .venv-release-verify
   . .venv-release-verify/bin/activate
   python -m pip install -U pip
   python -m pip install sdetkit==X.Y.Z
   python -m sdetkit --help
   python -m pip show sdetkit
   ```

9. Confirm index/release pages:
   - `https://pypi.org/project/sdetkit/X.Y.Z/` is reachable.
   - GitHub Release for `vX.Y.Z` includes dist artifacts.

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


## Record public verification evidence

After completing external-user verification for a real release, add a short record to `docs/release-verification.md` using the page template.

Keep entries factual and minimal:
- exact released version
- exact install and validation commands run
- verifier environment (OS, Python, pip)
- success signals + links (PyPI version page and GitHub Release)
- support path if users cannot install

Do not add a verification entry unless the release was actually published and validated externally.

## Optional TestPyPI rehearsal

Before first real publish, maintainers can rehearse upload/install manually:

```bash
python -m build
python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple sdetkit==X.Y.Z
```

This is optional and not wired to the default release workflow.
