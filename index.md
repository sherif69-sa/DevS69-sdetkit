# DevS69 SDETKit project index

Use this file as the repository-level landing page when browsing the source tree. The product README stays concise; the detailed operator and artifact guidance lives under `docs/`.

## First paths

| Need | Open |
| --- | --- |
| Product overview and install | [README.md](README.md) |
| Documentation home | [docs/index.md](docs/index.md) |
| Documentation map | [docs/docs-map.md](docs/docs-map.md) |
| Daily operator runbook | [docs/operator-essentials.md](docs/operator-essentials.md) |
| Investigation and diagnosis | [docs/investigation-operator-guide.md](docs/investigation-operator-guide.md) |
| Runtime and uploaded artifacts | [docs/artifact-reference.md](docs/artifact-reference.md) |
| Generated/sample artifact directory | [docs/artifacts/README.md](docs/artifacts/README.md) |

## Safety reminder

SDETKit is evidence-first. Investigation, diagnosis, recommendation, and planning outputs are diagnostic/report-only by default. Repository mutation requires explicit guarded policy and PR-only remediation controls.

## Repository areas

| Area | Purpose |
| --- | --- |
| `src/` | Python package implementation. |
| `tests/` | Unit, workflow, docs, and contract tests. |
| `docs/` | Human docs, operator runbooks, references, and generated/sample artifact labels. |
| `docs/artifacts/` | Committed examples, proof packs, and historical closeout artifacts. |
| `docs/project/` | Project-level architecture, workflow, release, quality, and enterprise documents moved out of the root. |
| `.github/workflows/` | CI, quality, maintenance, and artifact upload workflows. |
| `scripts/`, `tools/` | Local validation and maintenance helpers. |
| `examples/`, `schemas/`, `config/` | Example inputs, schema contracts, and default configuration. |
