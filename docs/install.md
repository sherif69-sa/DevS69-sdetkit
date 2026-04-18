# Install SDETKit

Use this page for canonical installation paths before running release-confidence commands.

Python 3.11+ is required.

After install, continue with:
- Ultra-fast proof: [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md)
- Guided run: [First run quickstart (canonical)](ready-to-use.md)

## Recommended install path (first-time and external users)

Create a virtual environment first, then install from PyPI and verify CLI wiring:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install sdetkit==1.0.3
python -m sdetkit --help
```

Why this is the recommended path now:

- Avoids system Python `externally-managed-environment` failures on Ubuntu/WSL.
- Uses the public release surface directly.
- Works consistently for local first runs and CI smoke checks.

## Alternative install paths

Use these only if they better fit your environment.

### `pipx` (isolated CLI install)

```bash
pipx install sdetkit==1.0.3
pipx run sdetkit --help
```

### `uv tool install` (isolated tool install)

```bash
uv tool install sdetkit==1.0.3
uv tool run sdetkit --help
```

### Local source install (contributors in this repo)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install .
python -m sdetkit --help
```

## Runtime contract check (adopters and CI)

Use the adopter-focused runtime contract command to discover stable install/run surfaces:

```bash
python -m sdetkit contract runtime --format json
```

This prints:
- `runtime_contract_version` (versioned install/run contract identifier)
- canonical first path commands
- stable machine output contract details for `review --format operator-json`
- container runtime invocation examples

Use this as a first CI/script check before running gates.

## External repository usage (canonical handoff)

From the root of the repository you want to gate:

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

Then continue with:
- [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md)
- [First run quickstart](ready-to-use.md)
- [Release confidence explainer](release-confidence.md)

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

For end users, prefer PyPI (venv or `pipx`) and use GitHub-source installs only when you explicitly need unreleased changes.

- Maintainer release process summary: [Releasing sdetkit](releasing.md)
- Public verification log: [release-verification.md](release-verification.md)
