# Blank repo to value in 60 seconds

**Use this page if:** you want the fastest honest proof-of-value run in a fresh repo.

**Not this page:** for full installation choices use [Install](install.md); for team rollout use [Adoption](adoption.md).

## 60-second command flow

```bash
python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
python -m sdetkit --help
python -m sdetkit doctor
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --stable-json --out build/release-preflight.json
```

## What you get immediately

1. Environment confidence (`doctor`)
2. Deterministic gate results (`gate fast`, `gate release`)
3. Structured evidence in `build/`

```text
build/
├── gate-fast.json
└── release-preflight.json
```

## How to read artifacts

Use [CI artifact walkthrough (canonical)](ci-artifact-walkthrough.md) for the artifact-first review order.

## Next step

- Team rollout: [Adopt SDETKit in your repository](adoption.md)
- CI rollout: [Recommended CI flow](recommended-ci-flow.md)
- Comparison framing: [SDETKit vs ad hoc scripts and separate tools](sdetkit-vs-ad-hoc.md)
