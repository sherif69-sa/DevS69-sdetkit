# DevS69 SDETKit

SDETKit helps teams turn test + CI signals into clear release decisions, deterministic checks, and actionable failure insights.

## 60-second start

```bash
make bootstrap
bash quality.sh ci
python -m sdetkit kits list
```

Need the deepest whole-repo improvement lane? Run:

```bash
make max
```

## What this repo contains

```text
src/sdetkit/   # product code + CLI
tests/         # automated tests
docs/          # user and maintainer docs
examples/      # runnable examples
scripts/       # repo helper scripts
.sdetkit/      # local generated outputs
artifacts/     # generated evidence packs
```

## Use the right lane

- **Release confidence** → `python -m sdetkit release --help`
- **Test intelligence** → `python -m sdetkit intelligence --help`
- **Integration assurance** → `python -m sdetkit integration --help`
- **Failure forensics** → `python -m sdetkit forensics --help`

## Most-used commands

```bash
python -m sdetkit kits list
python -m sdetkit kits discover --goal "align all repo capabilities"
python -m sdetkit release gate release
python -m sdetkit intelligence failure-fingerprint --failures examples/kits/intelligence/failures.json
python -m sdetkit integration check --profile examples/kits/integration/profile.json
python -m sdetkit forensics compare --from examples/kits/forensics/run-a.json --to examples/kits/forensics/run-b.json --fail-on error
bash quality.sh verify
bash premium-gate.sh --mode full
```

## Discover hidden/advanced surfaces

```bash
python -m sdetkit --help
python -m sdetkit --help --show-hidden
python -m sdetkit kits discover --query "release integration forensics"
```

## Documentation

- Docs hub: [`docs/index.md`](docs/index.md)
- Project structure: [`docs/project-structure.md`](docs/project-structure.md)
- Cleanup policy: [`docs/repo-cleanup-plan.md`](docs/repo-cleanup-plan.md)
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Release process: [`RELEASE.md`](RELEASE.md)

## Root-level rules (short version)

- Keep root files project-wide only.
- Put implementation in `src/sdetkit/` and coverage in `tests/`.
- Put deep docs in `docs/`.
- Put generated outputs in `.sdetkit/` or `artifacts/`.

For full rules, use [`docs/repo-cleanup-plan.md`](docs/repo-cleanup-plan.md).
