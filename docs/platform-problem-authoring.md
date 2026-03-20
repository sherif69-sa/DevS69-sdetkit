# Platform-style Python problem authoring

## Product lane summary

`python -m sdetkit author problem ...` is the repo-owned workflow for autonomous platform-problem authoring against a pinned target repository.

This lane is designed for runs that only provide:

- `REPO_URL`
- `PINNED_SHA`

The workflow owns the environment-first contract itself:

- bootstraps `/work` and fallback ledger files,
- clones the target repo into `/work/app`,
- checks out the exact pinned SHA,
- inspects repo metadata and baseline commands,
- renders `Dockerfile.problem` from repo metadata,
- copies the rendered Dockerfile into `/work/docker.file`,
- builds and runs the authoring container through Python helpers,
- scaffolds novelty-gate and candidate-note templates,
- co-ordinates baseline/repo-fit/candidate-fit gating,
- validates patch boundaries and configured size gates,
- validates clean-tree replay with `git apply --check`,
- validates the base/new/solution triad,
- emits machine-readable doctor, run, and failure summaries.

## Stable artifact contract

Every authoring run targets these stable canonical output paths in `/work`:

- `/work/test.patch`
- `/work/solution.patch`
- `/work/docker.file`
- `/work/final_title.txt`
- `/work/final_description.txt`
- `/work/run_summary.json`

Additional machine-readable workflow outputs:

- `/work/author_doctor.json`
- `/work/final_failure.json` when the run fails honestly

After final packaging and verification complete, the workflow exports the latest bundle into this repository at `artifacts/platform_problem/latest/`:

- `artifacts/platform_problem/latest/test.patch`
- `artifacts/platform_problem/latest/solution.patch`
- `artifacts/platform_problem/latest/docker.file`
- `artifacts/platform_problem/latest/final_title.txt`
- `artifacts/platform_problem/latest/final_description.txt`
- `artifacts/platform_problem/latest/run_summary.json`
- `artifacts/platform_problem/latest/export_manifest.json`

If the run fails and `/work/final_failure.json` exists, the workflow also exports:

- `artifacts/platform_problem/latest/final_failure.json`

If the current repo strategy cannot produce a valid artifact bundle, the workflow does **not** silently pass. It writes the failure report and keeps the output contract stable.

## Command family

### 1) Bootstrap `/work`

```bash
python -m sdetkit author problem init --workdir /work --topic rich-stateful-contract
```

Creates or repairs:

- `/work/current_problem.txt`
- `/work/current_slug.txt`
- `/work/problem_history.md`
- `/work/novelty_gate/`
- `/work/novelty_gate.txt`
- `/work/candidate_notes.md`
- `/work/submission_<ID>/`
- `/work/test.patch`
- `/work/solution.patch`
- `/work/docker.file`
- `/work/final_title.txt`
- `/work/final_description.txt`
- `/work/run_summary.json`

### 2) Run the authoring doctor

```bash
python -m sdetkit author problem doctor --repo-root . --workdir /work --format json
```

Doctor checks:

- `git` availability,
- `docker` availability,
- writable `/work`,
- fallback ledger creation,
- target-repo metadata presence,
- inferred pytest/plugin dependency risks,
- likely long-horizon repo fit.

It writes `/work/author_doctor.json`.

### 3) Render `Dockerfile.problem`

```bash
python -m sdetkit author problem render-dockerfile --repo-root .
```

The renderer inspects, when present:

- `pyproject.toml`
- `tox.ini`
- `noxfile.py`
- `requirements*.txt`
- CI files

The generated Dockerfile always uses:

- `FROM public.ecr.aws/x8v8d7g8/mars-base:latest`
- `CMD ["/bin/bash"]`

Install steps are emitted at build time only. The lane does **not** depend on runtime `pip install`, `uv`, or opportunistic dependency mutation inside the container.

### 4) Verify the artifact bundle

```bash
python -m sdetkit author problem verify --repo-root . --workdir /work --format json
```

Verification covers:

- required artifact existence,
- `test.patch` boundary rules,
- `solution.patch` production-only rules,
- configured size gates,
- `docker.file` parity with `Dockerfile.problem`,
- clean-tree replay with `git apply --check`,
- base/new/solution triad expectations,
- final title and description constraints.

### 5) Run the full workflow

```bash
python -m sdetkit author problem run \
  --repo https://github.com/Textualize/rich \
  --sha ce0118819d172d134507bcf5982d3faf82bbc43e \
  --workdir /work \
  --min-test-patch-bytes 204800 \
  --min-solution-patch-bytes 29696
```

Current `run` behavior:

1. bootstraps `/work`,
2. clones the target repo into `/work/app`,
3. checks out the pinned SHA,
4. inspects metadata and environment fit,
5. renders `Dockerfile.problem`,
6. copies the rendered Dockerfile into `/work/docker.file`,
7. runs the authoring doctor,
8. builds and runs the authoring container in Python when Docker is enabled,
9. executes repo-owned baseline, repo-fit, candidate-fit, and novelty scaffolding stages,
10. verifies the artifact bundle and emits final summaries,
11. exports the final `/work` bundle into `artifacts/platform_problem/latest/` with an `export_manifest.json`.

If an automated authoring strategy matches the target repository, the run can finish with a verified artifact bundle. If not, the run still terminates cleanly with `/work/final_failure.json` and `/work/run_summary.json` explaining exactly where the workflow stopped.

## Runner contract

Generated `test.sh` follows the minimal platform style in spirit:

```bash
#!/usr/bin/env bash

set -euo pipefail

mode=${1:-}
case "$mode" in
  new) python3 -m pytest tests/test_<topic>_problem.py ;;
  base) python3 -m pytest tests --ignore=tests/test_<topic>_problem.py ;;
  *) echo "Usage: $0 {base|new}" >&2; exit 2 ;;
esac
```

When a repo uses `src/` layout, the workflow may add an inline `PYTHONPATH=src` prefix to preserve the same minimal runner shape without mutating the environment globally.

The verifier then checks:

- starter tree: `base` passes,
- starter tree plus `test.patch`: `new` fails,
- starter tree plus `test.patch` plus `solution.patch`: `base` passes and `new` passes.

## Workflow policy file

The machine-readable workflow contract lives at:

- `.sdetkit/workflows/platform_problem.yaml`

It records:

- gating order,
- required artifacts,
- default size gates,
- allowed `test.patch` paths,
- allowed `solution.patch` scope,
- preferred production-file breadth,
- runner contract,
- clean-tree replay sequence,
- base/new/solution triad sequence,
- novelty-gate sections,
- final title and description constraints,
- failure-summary fields.

## What is implemented today

Implemented now:

- the public `author problem` command family,
- machine-readable workflow config,
- `/work` bootstrap and ledger fallback,
- `Dockerfile.problem` rendering,
- Python-owned Docker build and container execution helpers,
- baseline/repo-fit/candidate-fit gate execution,
- novelty-gate and candidate-note scaffolding,
- patch-boundary verification,
- size-gate enforcement,
- clean-tree replay and triad verification,
- machine-readable doctor/run/failure summaries,
- smoke-style tests for both successful and failing workflow paths.

## Current remaining gap

The workflow engine is real and runnable, but automated problem synthesis is still strategy-based. Today the repo includes a smoke-fixture-backed authoring strategy that proves the full contract end to end for a controlled repository shape. For other cloned target repos, including `Textualize/rich`, the run will still execute the owned workflow and either:

- produce the stable artifact bundle when a matching strategy exists, or
- produce a concrete failure report describing why autonomous authoring did not finish yet.

That means the repo now owns the run contract, Docker/container lifecycle, verification rules, and final output paths, while future strategy expansion can deepen repo-specific authoring coverage without changing the command surface.
