# Install SDETKit

**Use this page if:** you need the canonical installation paths for local use, external repositories, or contributor setup.

**Next step:** after install, go to [First run quickstart (canonical)](ready-to-use.md).

## Recommended install path (first-time and external users)

Install directly from GitHub, then verify the CLI:

```bash
python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
python -m sdetkit --help
```

Why this is the recommended path now:

- Works in any repository without cloning this project first.
- Uses the same public source every team can access.
- Does not rely on this repository's helper scripts.
- Public PyPI install is not yet verified in this repository's release records.

## Alternative install paths

Use these only if they better fit your environment.

### `pipx` (isolated CLI install)

```bash
pipx install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
pipx run sdetkit --help
```

### `uv tool install` (isolated tool install)

```bash
uv tool install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
uv tool run sdetkit --help
```

### Local source install (contributors in this repo)

```bash
python -m pip install .
python -m sdetkit --help
```

## External repository usage (canonical handoff)

From the root of the repository you want to gate:

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
```

Then continue with:

- [First run quickstart](ready-to-use.md) for the beginner lane.
- [Adopt SDETKit in your repository](adoption.md) for team rollout and CI rollout.

## Development setup (this repository only)

If you are contributing to SDETKit itself:

```bash
bash scripts/bootstrap.sh
source .venv/bin/activate
python -m pip install -e .[dev,test,docs]
```

This setup is for contributors/maintainers, not required for external adoption.

## PyPI/public distribution posture

SDETKit has release automation for build, wheel validation, optional PyPI publish, and provenance attestation in `.github/workflows/release.yml`.

Until a release is publicly published and externally verified, the install recommendation remains GitHub URL install.

- Maintainer release process summary: [Releasing sdetkit](releasing.md)
- Public verification log: [release-verification.md](release-verification.md)
