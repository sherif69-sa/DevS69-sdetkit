# Quickstart (copy-paste)

Run from your target repository root.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install sdetkit==1.0.3

mkdir -p build
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

## Artifact triage order

1. `build/release-preflight.json`
2. `build/gate-fast.json`
3. raw logs only after artifact triage
