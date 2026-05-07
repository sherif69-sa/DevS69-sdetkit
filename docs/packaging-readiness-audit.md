# Packaging / install / release-readiness audit

This audit captures **small, safe** productization improvements focused on adoption friction for outside users.

## Scope reviewed

- Package metadata in `pyproject.toml`
- Install guidance in `README.md`
- External-adoption install guidance in `docs/adoption.md`
- Release/versioning discoverability in `docs/project/release-process.md`, `docs/releasing.md`, and changelog navigation

## What is already good

- Build backend and metadata are modern (`setuptools` + PEP 621 layout).
- CLI entry points are explicitly declared for `sdetkit`, `sdkit`, `kvcli`, and `apigetcli`.
- Semantic versioning and release tag/version matching are clearly documented.
- Release flow already includes build validation, twine checks, and wheel smoke testing.
- Changelog and release verification docs already exist and are linked from docs navigation.

## Friction points identified

1. **Install-method ambiguity for new adopters**
   - README previously focused on local `pip install .` without clearly separating local clone vs external adoption paths.
2. **Optional dependency discoverability was too thin**
   - Extras were listed as commands but not explained by purpose (required vs optional intent).
3. **Release discoverability from package metadata could be improved**
   - `pyproject.toml` URLs included changelog and release process, but not direct GitHub Releases page.

## Improvements made in this PR

- Added a direct **Releases** URL in package metadata (`[project.urls]`) for better discovery in package index metadata surfaces.
- Clarified README installation section to explicitly distinguish:
  - local/source install,
  - GitHub install for external adoption,
  - developer bootstrap path.
- Added an extras guidance table in README describing when to use each extra (`dev`, `test`, `docs`, `packaging`, `telegram`, `whatsapp`) and example combined install.

## Deferred for later PRs

- Publishing policy automation details beyond current docs (kept current flow unchanged).
- Potential future PyPI-first install guidance switch (only after confirmed public release availability and verification records).
- Any dependency or build-system restructuring.

## Safety notes

- No runtime behavior or command surface changed.
- No dependency versions changed.
- No packaging build flow changed.
- Changes are documentation/metadata only, so risk is low and review scope is small.
