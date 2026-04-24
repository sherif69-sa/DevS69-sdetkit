# Install SDETKit

Use this page to choose an install mode quickly before your first run.

Python 3.10+ is required.

After install, continue with:
- Fast onboarding: [Quickstart (copy-paste)](quickstart-copy-paste.md)
- Guided run: [First run quickstart (canonical)](ready-to-use.md)

## Choose an install mode

| If you need... | Use this mode |
| --- | --- |
| Project-local, repeatable setup (recommended for most users/teams) | `venv` |
| Isolated global CLI-style install | `pipx` |
| Local development of this repository | Local source install |

Do **not** rely on bare system `pip install ...` on Ubuntu/WSL; it may fail with an externally-managed-environment error. Use `venv` or `pipx` instead.

## Recommended: `venv` (project-local, first-time friendly)

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install sdetkit==1.0.3
python -m sdetkit --help
```

## `pipx` (isolated app-style install)

```bash
pipx install sdetkit==1.0.3
pipx run sdetkit --help
```

## Local source install (contributors in this repo)

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install .
python -m sdetkit --help
```

## Runtime contract check (adopters and CI)

Use the runtime contract command to confirm stable install/run surfaces:

```bash
python -m sdetkit contract runtime --format json
```

## External repository usage (canonical handoff)

From the root of the repository you want to gate:

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

Then continue with:
- [Quickstart (copy-paste)](quickstart-copy-paste.md)
- [First run quickstart](ready-to-use.md)
- [Release confidence explainer](release-confidence.md)

## Development setup (this repository only)

If you are contributing to SDETKit itself:

```bash
bash scripts/bootstrap.sh
source .venv/bin/activate
python -m pip install -e .[dev,test,docs]
```

This setup is for contributors/maintainers and is not required for external adoption.
