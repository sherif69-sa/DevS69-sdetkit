# CircleCI proof-command discovery

SDETKit can inspect repository-owned CircleCI configuration without calling the CircleCI API or running target-repository commands.

Run the read-only adoption surface:

```bash
python -m sdetkit adoption-surface \
  --root . \
  --out build/sdetkit/adoption-surface.json \
  --format report
```

## Evidence SDETKit reads

The adapter checks these repository paths:

```text
.circleci/config.yml
.circleci/config.yaml
```

When a top-level job contains a literal single-line `run` step, SDETKit can recommend that command for human review. The recommendation includes:

```text
ci_system=circleci
file=<config path>
job=<job name>
step_name=<optional run-step name>
purpose=<test|lint|type|security|docs|unknown>
auto_run_allowed=false
executes_untrusted_code=true
```

Supported literal shapes include:

```yaml
- run: python -m pytest -q
```

```yaml
- run:
    name: Lint
    command: python -m ruff check .
```

```yaml
- run: {name: Types, command: mypy src}
```

## Review-first behavior

SDETKit does not evaluate or guess behavior from:

- `setup: true` dynamic configuration;
- orbs or orb steps;
- pipeline or job parameters;
- reusable command bodies or invocations;
- CircleCI interpolation such as `<< pipeline.parameters.value >>`;
- shell variables or command substitution;
- multiline YAML command blocks;
- unsupported custom step mappings;
- multiple CircleCI config files where the active file cannot be inferred.

These signals are written to `review_first_unknowns` so an operator can inspect the native CircleCI configuration.

## Safety boundary

A recommended command is evidence, not authorization. SDETKit does not execute it automatically and does not mutate the target repository or CircleCI project.

```text
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
```

Orbs, parameters, dynamic configuration, remote behavior, contexts, secrets, and project settings remain outside this repository-only proof.

## Maintainer proof

```bash
python -m pytest -q tests/test_adoption_surface_circleci.py -o addopts=
python -m pytest -q \
  tests/test_adoption_surface_jenkins.py \
  tests/test_adoption_surface.py \
  -o addopts=
python -m pre_commit run -a
```
