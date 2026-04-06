# DevS69 SDETKit

DevS69 SDETKit gives engineering teams deterministic release go/no-go decisions with machine-readable evidence, using one repeatable command path from local to CI.

## Canonical first proof lane (start here)

Run this exact command path first:

```bash
python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --stable-json --out build/release-preflight.json
python -m sdetkit doctor
```

Expected first artifacts:

```text
build/
├── gate-fast.json
└── release-preflight.json
```

Inspect order:
1. `build/release-preflight.json` (`ok`, `failed_steps`, `profile`)
2. If `failed_steps` includes `gate_fast`, open `build/gate-fast.json` (`ok`, `failed_steps`, `profile`)
3. Use raw logs only after artifact triage

What success means:
- `release-preflight.json` has `ok: true`
- `gate-fast.json` has `ok: true`

What failure means:
- `ok: false` and/or non-empty `failed_steps` gives the first deterministic remediation target.

## Canonical local-to-CI journey

- Canonical first proof: [`docs/blank-repo-to-value-60-seconds.md`](docs/blank-repo-to-value-60-seconds.md)
- Canonical real-repo fixture proof: [`docs/real-repo-adoption.md`](docs/real-repo-adoption.md)
- Canonical CI rollout path: [`docs/recommended-ci-flow.md`](docs/recommended-ci-flow.md)
- Canonical artifact decoder: [`docs/ci-artifact-walkthrough.md`](docs/ci-artifact-walkthrough.md)

## Who this is for / not for

**Best fit**
- Teams that want deterministic release decisions instead of ad hoc interpretation.
- Engineers who need machine-readable evidence for PR/release review.
- Repos standardizing the same release checks in local and CI runs.

**Probably not a fit (yet)**
- Very low-risk repos that do not need structured release evidence.
- Teams that only want raw tool invocations with fully custom orchestration.

## Start here

- Install (canonical): [`docs/install.md`](docs/install.md)
- Blank repo proof in 60 seconds: [`docs/blank-repo-to-value-60-seconds.md`](docs/blank-repo-to-value-60-seconds.md)
- Guided run (same path): [`docs/ready-to-use.md`](docs/ready-to-use.md)
- Release-confidence model (canonical): [`docs/release-confidence.md`](docs/release-confidence.md)
- Root CLI grouping and canonical path view: `python -m sdetkit --help`
- Stability levels (policy boundary): [`docs/stability-levels.md`](docs/stability-levels.md) — understand what is stable vs advanced vs experimental
- Before/after evidence behavior: [`docs/before-after-evidence-example.md`](docs/before-after-evidence-example.md)
- Real evidence artifacts from this repo: [`docs/evidence-showcase.md`](docs/evidence-showcase.md)

## Secondary: broader surfaces and advanced lanes

These remain available after the core release-confidence lane is trusted.

### Extended repo lanes

```bash
make bootstrap
bash quality.sh ci
python -m sdetkit kits list
python -m sdetkit --help --show-hidden
```

### Repo health snapshot

```bash
PYTHONPATH=src pytest -q
bash quality.sh cov
ruff check .
mutmut results
```

### Project layout

```text
src/sdetkit/   # product code + CLI
tests/         # automated tests
docs/          # user and maintainer docs
examples/      # runnable examples
scripts/       # repo helper scripts
.sdetkit/      # local generated outputs
artifacts/     # generated evidence packs
```

## Documentation and references

- Docs hub: [`docs/index.md`](docs/index.md)
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Release process: [`RELEASE.md`](RELEASE.md)
- Enterprise readiness audit: [`docs/enterprise-readiness-audit-2026-04.md`](docs/enterprise-readiness-audit-2026-04.md)

### See also (secondary, after core lane is stable)

- Compare against ad hoc workflows: [`docs/sdetkit-vs-ad-hoc.md`](docs/sdetkit-vs-ad-hoc.md)
- Repo hygiene boundaries: [`docs/repo-cleanup-plan.md`](docs/repo-cleanup-plan.md)
- Ongoing repo status view: [`docs/repo-health-dashboard.md`](docs/repo-health-dashboard.md)
