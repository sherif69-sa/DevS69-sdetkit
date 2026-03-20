# Platform-style Python problem authoring

## What this lane is

`python -m sdetkit author problem ...` is the repo-owned workflow for preparing and validating platform-style Python problem authoring runs against a pinned target repository.

This lane is designed for later prompts that only provide:

- `REPO_URL`
- `PINNED_SHA`

The workflow owns the environment-first setup itself:

- bootstraps `/work` and fallback ledger files,
- renders `Dockerfile.problem` from target-repo metadata,
- drives `docker build` and `docker run` through Python helpers,
- scaffolds novelty-gate and candidate-notes templates,
- creates the stable artifact targets,
- verifies patch boundaries and configured size gates,
- verifies clean-tree replay with `git apply --check`,
- verifies the base/new triad,
- emits machine-readable doctor, run, and failure summaries.

## How this differs from gate / doctor / evidence / release

The existing product lanes remain focused on release confidence, repo readiness, deterministic evidence, and CI-facing go/no-go checks.

The authoring lane is different:

- it prepares a *target repository* for future problem authoring work,
- it enforces the artifact contract expected by platform-style review,
- it validates authoring-specific policies such as `test.patch` vs `solution.patch` boundaries,
- it centers the Dockerfile/problem-container workflow rather than release-report output.

This is a productized extension of the repo, not a replacement for the release-confidence surfaces.

## Command family

### Initialize `/work`

```bash
python -m sdetkit author problem init --workdir /work --topic refresh-contract
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

### Run the authoring doctor

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

### Render `Dockerfile.problem`

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

### Verify the artifact bundle

```bash
python -m sdetkit author problem verify --repo-root . --workdir /work --format json
```

Verification covers:

- required artifacts and metadata,
- `test.patch` boundary rules,
- `solution.patch` production-only rules,
- configured size gates,
- `docker.file` parity with `Dockerfile.problem`,
- clean-tree replay with `git apply --check`,
- base/new triad expectations.

### Run the full repo-owned workflow

```bash
python -m sdetkit author problem run \
  --repo https://github.com/example/project.git \
  --sha 0123456789abcdef0123456789abcdef01234567 \
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
7. generates the minimal repo-root `test.sh`,
8. runs the authoring doctor,
9. optionally runs `docker build` and `docker run`,
10. verifies the artifact bundle and emits summaries.

If the artifact bundle is incomplete, the workflow fails honestly and writes `/work/final_failure.json` with the concrete reason.

## Stable artifact contract

The workflow targets these stable paths:

- `/work/test.patch`
- `/work/solution.patch`
- `/work/docker.file`
- `/work/final_title.txt`
- `/work/final_description.txt`
- `/work/run_summary.json`

Additional machine-readable outputs:

- `/work/author_doctor.json`
- `/work/final_failure.json` on failure

## Workflow contract and policy file

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
- base/new triad sequence,
- novelty-gate sections,
- final title / description constraints,
- failure-summary fields.

## Patch-boundary policy

`test.patch` is expected to contain only:

- repo-root `test.sh`,
- exactly one new `tests/test_<topic>_problem.py`,
- the rare allowed test-side metadata edit when explicitly reviewed.

`solution.patch` is expected to contain only production files.

The verifier rejects leaked production files in `test.patch`, and rejects leaked tests, metadata, or Docker assets in `solution.patch`.

## Minimal runner contract

Generated `test.sh` follows the platform shape in spirit:

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

The verifier then checks:

- base passes on the starter tree,
- the new suite fails before the solution is applied,
- base and new both pass after the solution is applied.

## What is implemented today vs. what still depends on the later real task

Implemented now:

- the command family,
- machine-readable workflow config,
- workdir bootstrap and ledger fallback,
- Dockerfile.problem rendering,
- Docker build/run helpers,
- patch-boundary verification,
- size-gate enforcement,
- clean-tree replay and triad verification,
- machine-readable doctor/run/failure summaries,
- smoke-style tests for the new subsystem.

Still dependent on the later real authoring run:

- choosing a strong candidate contract in the cloned target repo,
- co-developing the final `test.patch` and `solution.patch`,
- producing the final title and constrained description for the actual target repository,
- reaching the final verified artifact bundle for that repo.

That separation is intentional and honest: this repo now owns the workflow engine and validation contract, while the later real-task run still supplies the concrete target-repo authoring decisions.
