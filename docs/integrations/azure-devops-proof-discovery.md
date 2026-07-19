# Azure DevOps proof-command discovery

SDETKit detects checked-in root pipeline files named `azure-pipelines.yml` or `azure-pipelines.yaml` and conservatively extracts literal commands from `script`, `bash`, `pwsh`, and `powershell` steps.

## What the adapter reports

For each accepted literal command, the adoption-surface artifact retains:

- `ci_system=azure_devops`;
- the repository-owned pipeline file;
- the job name, or `pipeline` when no job is declared;
- the script key that supplied the command;
- the inferred proof purpose and medium confidence;
- `auto_run_allowed=false` and `executes_untrusted_code=true`.

The command is a recommendation for a human to run in a trusted environment. Discovery does not execute the command.

## Review-first boundaries

SDETKit does not evaluate or expand:

- templates or `extends` references;
- compile-time or runtime expressions;
- variables or variable groups;
- strategies or matrices;
- task implementations;
- deployment environments;
- service connections or external resources;
- multiline script blocks;
- multiple pipeline-file precedence.

These surfaces appear in `review_first_unknowns` rather than being guessed.

## Example

```yaml
jobs:
  - job: quality
    steps:
      - script: python -m pytest -q
      - bash: python -m ruff check .
```

The two literal commands become source-grounded proof recommendations. A step such as `script: $(TEST_COMMAND)` remains unresolved.

## Proof

```bash
python -m pytest -q tests/test_adoption_surface_azure_devops.py -o addopts=
python -m pytest -q tests/test_adoption_surface_circleci.py tests/test_adoption_surface.py -o addopts=
python -m mypy src/sdetkit/adoption_surface/azure_devops.py
python -m pre_commit run -a
NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict
```

## Authority boundary

```text
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
```

No Azure DevOps pipeline, project, service connection, repository, branch, issue, or pull request is mutated.