# DevS69 SDETKit

DevS69 SDETKit gives engineering teams deterministic release go/no-go decisions with machine-readable evidence, using one repeatable command path from local to CI.

Use the same three commands everywhere (`gate fast`, `gate release`, `doctor`) so release decisions are consistent across developer machines and CI.

## 60-second first run

```bash
python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --stable-json --out build/release-preflight.json
python -m sdetkit doctor
```

## Expected artifacts and what to inspect first

```text
build/
├── gate-fast.json
└── release-preflight.json
```

Check these keys first:
- `ok` → pass/fail decision
- `failed_steps` → first triage targets
- `profile` → gate profile used

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
- Release-confidence model (canonical): [`docs/release-confidence.md`](docs/release-confidence.md)
- Before/after evidence behavior: [`docs/before-after-evidence-example.md`](docs/before-after-evidence-example.md)
- Real evidence artifacts from this repo: [`docs/evidence-showcase.md`](docs/evidence-showcase.md)

## Guided onboarding path (first 10 minutes)

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --stable-json --out build/release-preflight.json
python -m sdetkit doctor
```

Then continue with:
- [Choose your path](docs/choose-your-path.md)
- [Decision guide](docs/decision-guide.md)
- [Recommended CI flow](docs/recommended-ci-flow.md)

## Secondary: broader surfaces and advanced lanes

These remain available when you already have the core release-confidence lane working.

### Additional command families (only after core lane is stable)

- Release confidence is the primary lane.
- Other command families remain available through the CLI reference and kits docs.

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

## Root-level rules (short version)

- Keep root files project-wide only.
- Put implementation in `src/sdetkit/` and coverage in `tests/`.
- Put deep docs in `docs/`.
- Put generated outputs in `.sdetkit/` or `artifacts/`.

For full rules, use [`docs/repo-cleanup-plan.md`](docs/repo-cleanup-plan.md).
