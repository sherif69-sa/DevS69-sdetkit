# DevS69 SDETKit

![CI](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/ci.yml/badge.svg?branch=main)
![Quality](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/quality.yml/badge.svg?branch=main)
![Security](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/security.yml/badge.svg?branch=main)
![Repo Audit](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/repo-audit.yml/badge.svg?branch=main)
![Pages](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/pages.yml/badge.svg?branch=main)

Production-ready SDET + DevOps toolkit for deterministic diagnostics, API validation, policy gates, and release evidence.

## Product vision

SDETKit is designed as an **execution layer for trusted delivery**:

- **Reliability first**: deterministic outputs, explicit exit codes, CI-safe behavior.
- **Readiness by default**: quality, security, and release controls in one workflow.
- **Adoption-focused UX**: clear command groups, practical docs, and role-based paths.

## Product direction (next 30 days)

To evolve this repository into a focused product, we are prioritizing one primary use-case:

- **Release Confidence Engine for SDET/DevOps teams**
- Goal: provide deterministic, repeatable evidence that a repository is safe to ship.

Start with the focused strategy checklist:

- `docs/product-strategy.md`
- `docs/global-production-transformation-playbook.md`

Fast path to run the "release confidence" workflow:

```bash
bash ci.sh quick --skip-docs
bash quality.sh cov
python -m sdetkit security check --root . --baseline tools/security.baseline.json --format json
python -m sdetkit gate release
```

## Installation

### Runtime install

```bash
python -m pip install .
```

### Developer install (recommended)

```bash
bash scripts/bootstrap.sh
source .venv/bin/activate
```

### Optional extras

```bash
python -m pip install .[dev]
python -m pip install .[test]
```

## 2-minute quickstart

```bash
bash scripts/ready_to_use.sh quick
```

Manual equivalent:

```bash
python -m sdetkit --help
python -m sdetkit doctor --help
bash ci.sh quick --skip-docs
```

Ready-to-use guide: `docs/ready-to-use.md`

For full docs UX, open: <https://sherif69-sa.github.io/DevS69-sdetkit/>.

## Role-based starting paths

| Role | Start here | Why |
| --- | --- | --- |
| SDET / QA | `python -m sdetkit doctor --help` | Validate local/repo health quickly. |
| DevOps / Platform | `python -m sdetkit gate fast` | Run CI-equivalent quality lane locally. |
| Security / Governance | `python -m sdetkit security --help` | Apply policy and budget controls deterministically. |
| Maintainers | `python -m sdetkit evidence --help` | Generate and review release evidence artifacts. |

## Readiness model

Use this sequence for a release-ready posture:

```bash
bash ci.sh quick --skip-docs
bash quality.sh cov
python -m sdetkit security check --root . --baseline tools/security.baseline.json --format json
python -m sdetkit gate release
```

## UX-focused command architecture

Core domains:

- `doctor`: repository and environment diagnostics
- `repo`: repository audit + reporting
- `apiget` / `cassette-get`: deterministic API checks and replays
- `security`: policy/security workflows and budget enforcement
- `report`: deterministic report generation
- `ops` / `notify`: operations and communication automation
- `docs-qa` / `docs-nav`: docs health and navigation integrity
- `evidence` / `roadmap`: governance and planning support

List all commands:

```bash
python -m sdetkit --help
python -m sdetkit playbooks
```

## CI/CD integration

### GitHub Actions

```yaml
- name: Install
  run: python -m pip install .[dev,test]
- name: CI gate
  run: bash ci.sh quick --skip-docs
```

### Jenkins

See `examples/ci/jenkins/` (for example `jenkins-advanced-reference.Jenkinsfile`).

### Docker

```bash
docker build -t sdetkit .
docker run --rm -v "$PWD:/work" -w /work sdetkit python -m sdetkit gate fast
```

## Continuous upgrade lane

```bash
python -m sdetkit day90-phase3-wrap-publication-closeout --format json --strict
python -m sdetkit day91-continuous-upgrade-closeout --format json --strict
python -m sdetkit day92-continuous-upgrade-cycle2-closeout --format json --strict
python -m sdetkit day93-continuous-upgrade-cycle3-closeout --format json --strict
```

## Documentation

- Docs portal: <https://sherif69-sa.github.io/DevS69-sdetkit/>
- Local build: `mkdocs build -s`
- Determinism checklist: `docs/determinism-checklist.md`

## Contributing

```bash
bash scripts/bootstrap.sh
source .venv/bin/activate
bash quality.sh cov
```

Before opening a PR, prefer running `bash quality.sh full-test` when feasible.

## License

Distributed under the Apache-2.0 license. See `LICENSE` and `ENTERPRISE_OFFERINGS.md`.
