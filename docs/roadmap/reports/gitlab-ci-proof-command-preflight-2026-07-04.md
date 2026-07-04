# GitLab CI proof-command extraction preflight — 2026-07-04

This preflight narrows issue #1944 before implementation. The goal is to keep the
first implementation PR small, reviewable, and conservative.

## Target slice

Implement read-only extraction from `.gitlab-ci.yml` for simple top-level jobs
that define literal `script:` commands.

Supported first-slice forms:

```yaml
unit:
  script: npm test

lint:
  script:
    - npm run lint
    - npm run typecheck
```

## Explicit non-goals for the first slice

- Do not execute CI jobs.
- Do not fetch remote includes.
- Do not evaluate inheritance, `extends`, `rules`, or matrix expansion.
- Do not resolve shell interpolation or YAML anchors as authoritative commands.
- Do not change GitHub Actions, Jenkins, or existing language detection behavior.

## Reserved keys to ignore

The extractor should skip GitLab configuration keys that are not jobs:

- `stages`
- `variables`
- `workflow`
- `include`
- `default`
- `image`
- `services`
- `before_script`
- `after_script`
- `cache`

## Command classification policy

Candidate commands should remain advisory and review-first. Purpose can be
classified from obvious tokens only:

| Purpose | Example command signals |
| --- | --- |
| test | `test`, `pytest`, `go test`, `cargo test`, `mvn test`, `dotnet test` |
| lint | `lint`, `ruff`, `eslint`, `flake8`, `clippy` |
| type | `typecheck`, `tsc`, `mypy`, `pyright` |
| security | `audit`, `govulncheck`, `trivy`, `semgrep`, `bandit` |
| unknown | anything not confidently classified |

## Safety and authority requirements

Every extracted command must preserve the existing adoption-surface authority
boundary:

- `auto_run_allowed=false`
- `executes_untrusted_code=true`
- `automation_allowed=false`
- `patch_application_allowed=false`
- `merge_authorized=false`
- `semantic_equivalence_proven=false`

Dynamic or unresolved configuration should be reported through
`review_first_unknowns` instead of guessed.

## Focused verification for implementation PR

```bash
python -m pytest -q tests/test_adoption_surface.py -o addopts=
python -m mypy src
python -m pre_commit run -a
```

## Suggested implementation shape

Keep the production change isolated in `src/sdetkit/adoption_surface.py`:

1. Add a small helper that reads `.gitlab-ci.yml` if present.
2. Parse only simple mappings and literal `script:` strings/lists.
3. Add proof commands using the existing `_add_proof_command()` path.
4. Store `.gitlab-ci.yml` plus the job name in command evidence only if the
   current schema can carry it without breaking validators; otherwise keep
   evidence in `review_first_unknowns` or defer schema expansion.
5. Add regression coverage in `tests/test_adoption_surface.py`.

The implementation PR should remain one issue, one parser slice, and one focused
proof surface.
